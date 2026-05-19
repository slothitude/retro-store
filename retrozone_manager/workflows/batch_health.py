"""Batch Health Check workflow — sell-through analysis, batch recommendations."""
from .base import BaseWorkflow


class BatchHealth(BaseWorkflow):
    name = "Batch Health Check"
    description = "Sell-through analysis and batch recommendations"
    risk_level = "medium"

    def get_steps(self):
        return [
            {"name": "Analyze Batches", "type": "analyze"},
            {"name": "Propose Changes", "type": "propose"},
            {"name": "Execute Changes", "type": "execute"},
        ]

    def build_analyze_prompt(self):
        batches = self.db.get_batches()
        products = {p["slug"]: p for p in self.db.get_products()}

        from db import get_batch_phase, get_batch_price, get_batch_remaining
        from datetime import datetime

        batch_text = ""
        for b in batches:
            remaining = get_batch_remaining(b)
            phase = get_batch_phase(b) if b['status'] == 'active' else b['status']
            price = get_batch_price(b) if b['status'] == 'active' else 0
            cost = b['cost_per_unit_cents']
            margin_pct = ((price - cost) / cost * 100) if cost and price else 0
            capital_tied = remaining * cost

            try:
                created = b.get('created_at', b.get('ordered_at', ''))
                days_active = max(1, (datetime.utcnow() - datetime.fromisoformat(created)).days)
            except (ValueError, TypeError):
                days_active = 1
            daily_vel = b['units_sold'] / days_active
            days_to_sellout = (remaining / daily_vel) if daily_vel > 0 else float('inf')

            batch_text += (
                f"  Batch #{b['id']}: {b.get('product_name', b['product_slug'])} "
                f"({b['units_sold']}/{b['units_total']} sold, {remaining} left) "
                f"phase={phase} cost=${cost/100:.2f} price=${price/100:.2f if price else 0} "
                f"margin={margin_pct:.0f}% velocity={daily_vel:.2f}/day "
                f"days_to_sellout={'%.0f' % days_to_sellout if days_to_sellout != float('inf') else 'STALLED'} "
                f"capital_tied=${capital_tied/100:.2f} "
                f"arrives={b['arrives_at'][:10]} expires={b['expires_at'][:10]} status={b['status']}\n"
            )

        if not batch_text:
            batch_text = "  (no batches)"

        now = datetime.utcnow().isoformat()[:10]

        return f"""Analyze batch health for RetroZone (today: {now}).

Evaluate EVERY batch through three lenses:

**ROI**: What's the actual margin? Is capital sitting idle? Which batches are earning their keep?
**VELOCITY**: How fast is each batch turning? Stalled batches = dead money. Flag anything with velocity < 0.1/day urgently.
**ETHOS**: Are clearance prices genuinely fair to customers? Are we dumping stock ethically or just panicking?

Return:
- EARNING: batches with good velocity and margin
- STALLED: low/zero velocity — capital trapped
- AT RISK: may not sell out before expiry
- EXPIRED/EXPIRING: needs immediate action
- ROI SUMMARY: total capital deployed, total earned, efficiency ratio
- VELOCITY RANKING: fastest to slowest batch
- ETHOS FLAGS: anything concerning

BATCHES:
{batch_text}"""

    def build_propose_prompt(self, analyze_result):
        return f"""Based on your batch analysis:
{analyze_result}

Propose specific batch changes as a JSON array. Each action:
- "description": e.g. "Mark batch #1 as clearance" or "Deactivate stalled batch #3"
- "reason": why, referencing ROI/velocity/ethos
- "sql": the exact SQL
- "reversible": true for status changes
- "risk": "medium" for batch changes

Do NOT propose spending money (new orders). That's a separate workflow.
Return ONLY the JSON array."""
