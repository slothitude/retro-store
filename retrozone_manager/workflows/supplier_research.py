"""Supplier Research workflow — find + compare suppliers on Alibaba."""
from .base import BaseWorkflow


class SupplierResearch(BaseWorkflow):
    name = "Supplier Research"
    description = "Find + compare suppliers on Alibaba"
    risk_level = "medium"

    def __init__(self, product_query=""):
        super().__init__()
        self.product_query = product_query

    def get_steps(self):
        return [
            {"name": "Research Suppliers", "type": "research",
             "timeout": 300},
            {"name": "Analyze Results", "type": "analyze"},
            {"name": "Propose Best Suppliers", "type": "propose"},
            {"name": "Save Suppliers", "type": "execute"},
        ]

    def build_research_prompt(self) -> str:
        return (
            f"Search Alibaba for '{self.product_query}' products suitable for RetroZone (Australian gaming store).\n\n"
            "Use search_alibaba to find products. For the top 3-5 most relevant results, "
            "use get_alibaba_product_details to get full pricing and specs.\n\n"
            "Also check AliExpress retail pricing with search_aliexpress to understand the retail landscape.\n\n"
            "For each supplier found, report:\n"
            "- Product name and URL\n"
            "- Price range (USD, estimate AUD at 1.55x)\n"
            "- MOQ (minimum order quantity)\n"
            "- Supplier name and rating\n"
            "- Key specs relevant to gaming handhelds\n"
            "- Estimated shipping to Australia\n\n"
            "Finally, list any existing tracked suppliers with list_suppliers to compare."
        )

    def build_analyze_prompt(self) -> str:
        research = self.db._conn().execute(
            "SELECT step_results FROM workflow_temp WHERE step = 'research'"
        ).fetchone() if False else ""

        return (
            "Analyze the supplier research results from the previous step.\n\n"
            "Evaluate each supplier through our three lenses:\n"
            "- ROI: What's the margin between wholesale cost and our retail price?\n"
            "- VELOCITY: Is this a product that sells fast? Check store data.\n"
            "- ETHOS: Does this product serve our mission of affordable gaming?\n\n"
            "Compare wholesale prices to our current store prices and to eBay market prices.\n"
            "Identify the best 2-3 suppliers with the highest margin potential."
        )

    def build_propose_prompt(self, analyze_result: str) -> str:
        return (
            f"Based on supplier analysis:\n{analyze_result}\n\n"
            "Propose which suppliers to add to our tracker. Each action:\n"
            '- "description": e.g. "Add supplier XYZ Corp for R36S handhelds"\n'
            '- "reason": ROI/velocity/ethos justification\n'
            '- "supplier_name": supplier name\n'
            '- "url": product URL\n'
            '- "contact_email": supplier email if found, else ""\n'
            '- "category": product category\n'
            '- "rating": 1-5 based on Alibaba rating\n'
            '- "notes": key details (price, MOQ, shipping)\n\n'
            "Return ONLY a JSON array of supplier additions."
        )

    def parse_proposals(self, claude_response: str) -> list:
        import json, re
        text = claude_response.strip()
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return [{"description": "Review supplier research (no parseable actions)", "reason": text[:200],
                 "risk": "low", "supplier_name": "", "url": "", "contact_email": "",
                 "category": "", "rating": 0, "notes": ""}]

    def execute_action(self, action: dict):
        from ..mcp_server.tools.supplier_tracker import add_supplier
        result = add_supplier(
            name=action.get("supplier_name", ""),
            url=action.get("url", ""),
            contact_email=action.get("contact_email", ""),
            category=action.get("category", ""),
            rating=action.get("rating", 0),
            notes=action.get("notes", ""),
        )
        return result
