"""eBay Listing workflow — prepare and publish eBay listings from products."""
import json
from .base import BaseWorkflow


class EbayListing(BaseWorkflow):
    name = "eBay Listing"
    description = "Prepare and publish product listings to eBay"
    risk_level = "high"

    def __init__(self, product_slug=""):
        super().__init__()
        self.product_slug = product_slug

    def get_steps(self):
        return [
            {"name": "Analyze Product", "type": "analyze"},
            {"name": "Research Market", "type": "research", "timeout": 300},
            {"name": "Propose Listing", "type": "propose"},
            {"name": "Create Listing", "type": "execute"},
        ]

    def build_analyze_prompt(self) -> str:
        product = self.db.get_product(self.product_slug)
        if not product:
            return f"Product '{self.product_slug}' not found."

        from ..ebay_listing_builder import build_title, build_item_specifics, build_category_id

        title = build_title(product)
        specifics = build_item_specifics(product)
        category = build_category_id(product)

        # Get batch cost for pricing
        batches = self.db.get_active_batches()
        batch = next((b for b in batches if b["product_slug"] == self.product_slug), None)
        cost_info = f"Batch cost: ${batch['cost_per_unit_cents']/100:.2f}/unit" if batch else "No active batch"

        return (
            f"Prepare an eBay listing for:\n\n"
            f"Product: {product['name']} ({product['slug']})\n"
            f"Web price: ${product['price_cents']/100:.2f}\n"
            f"Stock: {product.get('stock', 0)}\n"
            f"{cost_info}\n"
            f"Specs: {product.get('specs', '{}')}\n\n"
            f"Generated eBay title ({len(title)} chars): {title}\n"
            f"Category ID: {category}\n"
            f"Item specifics: {json.dumps(specifics, indent=2)}\n\n"
            f"Evaluate this product for eBay AU listing. Consider:\n"
            f"- Is the title keyword-optimized and under 80 chars?\n"
            f"- Are item specifics complete for handheld gaming?\n"
            f"- Is the price competitive vs eBay market?\n"
            f"- Any compliance issues (Australian Consumer Law)?"
        )

    def build_research_prompt(self) -> str:
        return (
            f"Research eBay AU market for product '{self.product_slug}'.\n\n"
            f"Use search_ebay_sold to find what similar items ACTUALLY sold for.\n"
            f"Use search_ebay_active to see current competitor listings.\n"
            f"Use compare_channel_pricing to see our web vs eBay pricing.\n\n"
            f"Report:\n"
            f"- Average sold price and range\n"
            f"- Top competitor listings (titles, prices)\n"
            f"- Recommended price point for our listing\n"
            f"- Keywords competitors are using that we should include"
        )

    def build_propose_prompt(self, analyze_result: str) -> str:
        return (
            f"Based on product analysis and market research:\n{analyze_result}\n\n"
            f"Propose an eBay listing for product '{self.product_slug}'. Each action:\n"
            f'- "description": e.g. "Create eBay listing for R36S"\n'
            f'- "reason": pricing/competitive justification\n'
            f'- "product_slug": the product slug\n'
            f'- "ebay_price_cents": recommended eBay price in cents\n'
            f'- "quantity": how many to list\n'
            f'- "title": the eBay listing title (max 80 chars)\n'
            f'- "notes": any special notes\n\n'
            f"Return ONLY a JSON array of listing proposals."
        )

    def parse_proposals(self, claude_response: str) -> list:
        import re
        text = claude_response.strip()
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return [{
            "description": f"Create eBay listing for {self.product_slug}",
            "reason": text[:200],
            "risk": "high",
            "product_slug": self.product_slug,
            "ebay_price_cents": 0,
            "quantity": 1,
            "title": "",
            "notes": "",
        }]

    def execute_action(self, action: dict):
        """Create eBay listing draft in the database."""
        from ..mcp_server.db.schema import get_conn
        from datetime import datetime

        product_slug = action.get("product_slug", self.product_slug)
        sku = f"RZ-{product_slug}"
        ebay_price_cents = action.get("ebay_price_cents", 0)

        if not ebay_price_cents:
            # Fallback to web price + 5%
            product = self.db.get_product(product_slug)
            ebay_price_cents = int(product["price_cents"] * 1.05) if product else 0

        conn = get_conn()
        try:
            # Upsert listing draft
            existing = conn.execute(
                "SELECT id FROM ebay_listings WHERE sku = ?", (sku,)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE ebay_listings SET ebay_price_cents = ?, quantity_listed = ?, "
                    "notes = ?, updated_at = ? WHERE sku = ?",
                    (ebay_price_cents, action.get("quantity", 1),
                     action.get("notes", ""), datetime.utcnow().isoformat(), sku)
                )
                return f"Updated eBay listing draft: {sku} at ${ebay_price_cents/100:.2f}"
            else:
                conn.execute(
                    "INSERT INTO ebay_listings "
                    "(product_slug, sku, ebay_price_cents, status, quantity_listed, notes) "
                    "VALUES (?, ?, ?, 'draft', ?, ?)",
                    (product_slug, sku, ebay_price_cents,
                     action.get("quantity", 1), action.get("notes", ""))
                )
                conn.commit()
                return f"Created eBay listing draft: {sku} at ${ebay_price_cents/100:.2f}"
        except Exception as e:
            return f"Error creating listing: {e}"
        finally:
            conn.close()
