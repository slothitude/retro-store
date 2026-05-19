"""Order Review workflow — review orders, flag suspicious, propose status updates."""
import json
from .base import BaseWorkflow


class OrderReview(BaseWorkflow):
    name = "Order Review"
    description = "Review new orders, flag risky ones"
    risk_level = "low"

    def get_steps(self):
        return [
            {"name": "Analyze Orders", "type": "analyze"},
            {"name": "Propose Updates", "type": "propose"},
            {"name": "Execute Updates", "type": "execute"},
        ]

    def build_analyze_prompt(self):
        orders_24h = self.db.get_orders_since(24)
        pending = self.db.get_orders(status="pending")
        paid = self.db.get_orders(status="paid")

        all_orders = orders_24h + [o for o in pending + paid if o not in orders_24h]
        seen = set()
        unique = []
        for o in all_orders:
            if o["id"] not in seen:
                seen.add(o["id"])
                unique.append(o)

        orders_text = "\n".join(
            f"  #{o['id']}: email={o['email']}, name={o.get('name','')}, "
            f"total=${o['total_cents']/100:.2f}, status={o['status']}, "
            f"items={o['items_json']}, created={o['created_at'][:16]}"
            for o in unique
        ) or "  (no orders to review)"

        return f"""Review these orders for RetroZone.

For each order, evaluate through our three lenses:

1. **VELOCITY** — Is this order moving through the pipeline fast enough? Paid orders sitting unshipped = velocity drain. Flag any paid order older than 24h.
2. **ROI** — What's the margin on this order? Flag any order where items_json pricing seems wrong vs current batch pricing.
3. **ETHOS** — Does anything look suspicious or like someone's being taken advantage of?

Return:
- VELOCITY ISSUES: orders bottlenecked at any stage
- ROI FLAGS: pricing discrepancies or margin concerns
- SUSPICIOUS: orders that look risky
- READY TO SHIP: paid orders needing action
- SUMMARY: count by status, total revenue at stake

ORDERS:
{orders_text}"""

    def build_propose_prompt(self, analyze_result):
        return f"""Based on your order analysis:
{analyze_result}

Propose specific status updates as a JSON array. Each action:
- "description": e.g. "Mark order #5 as shipped"
- "reason": why, referencing ROI/velocity/ethos
- "sql": the exact SQL (e.g. "UPDATE orders SET status='shipped', updated_at=datetime('now') WHERE id=5")
- "reversible": true for status changes
- "risk": "low" for standard status changes, "medium" if uncertain

Only propose changes you're confident about. If nothing needs changing, return [].
Return ONLY the JSON array."""
