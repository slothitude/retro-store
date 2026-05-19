"""Price Monitor workflow — check competitor eBay pricing and compare with store."""
from .base import BaseWorkflow


class PriceMonitor(BaseWorkflow):
    name = "Price Monitor"
    description = "Check competitor eBay pricing"
    risk_level = "low"

    def __init__(self, product_query=""):
        super().__init__()
        self.product_query = product_query

    def get_steps(self):
        return [
            {"name": "Research eBay Prices", "type": "research",
             "timeout": 300},
            {"name": "Analyze vs Store Prices", "type": "analyze"},
            {"name": "Propose Adjustments", "type": "propose"},
        ]

    def build_research_prompt(self) -> str:
        return (
            f"Research current eBay pricing for '{self.product_query}' to compare with RetroZone store prices.\n\n"
            "Do BOTH:\n"
            f"1. search_ebay_sold('{self.product_query}') — what items ACTUALLY sold for (real market value)\n"
            f"2. search_ebay_active('{self.product_query}') — what competitors are asking right now\n\n"
            "Also check our current products with matching names in the store state.\n"
            "Return all pricing data found — sold prices, active asking prices, conditions, and shipping costs."
        )

    def build_analyze_prompt(self) -> str:
        products = self.db.get_products()
        products_text = "\n".join(
            f"  {p['name']} ({p['slug']}): ${p['price_cents']/100:.2f} "
            f"(compare: ${p.get('compare_price_cents', 0)/100:.2f}) stock={p['stock']}"
            for p in products
        )

        return (
            f"Compare the eBay pricing research against our current store prices.\n\n"
            "OUR CURRENT PRICES:\n"
            f"{products_text}\n\n"
            "For each product, analyze:\n"
            "1. MARKET PRICE: What's the real selling price on eBay? (sold listings, not asking)\n"
            "2. OUR PRICE: How does our price compare? Are we competitive?\n"
            "3. MARGIN: If we bought at Alibaba wholesale prices, what's the margin vs eBay sold price?\n"
            "4. OPPORTUNITY: Are there products we should stock but don't?\n"
            "5. THREATS: Are competitors undercutting us significantly?\n\n"
            "Evaluate through ROI/Velocity/Ethos lenses."
        )

    def build_propose_prompt(self, analyze_result: str) -> str:
        return (
            f"Based on price analysis:\n{analyze_result}\n\n"
            "Propose pricing adjustments or product additions. Each action:\n"
            '- "description": what to change\n'
            '- "reason": market justification\n'
            '- "sql": price update SQL if applicable (or "—" for suggestions)\n'
            '- "reversible": true/false\n'
            '- "risk": "low"/"medium"/"high"\n\n'
            "Be conservative — don't race to the bottom. Our value proposition includes "
            "local shipping, warranty support, and curated products.\n"
            "Return ONLY the JSON array."
        )
