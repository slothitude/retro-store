"""Reorder Recommendation workflow — sales velocity analysis, reorder suggestions."""
from .base import BaseWorkflow


class ReorderRecommendation(BaseWorkflow):
    name = "Reorder Recommendation"
    description = "Sales velocity analysis and reorder suggestions"
    risk_level = "high"

    def get_steps(self):
        return [
            {"name": "Analyze Sales Velocity", "type": "analyze"},
            {"name": "Propose Reorders", "type": "propose"},
            {"name": "Execute Reorders", "type": "execute"},
        ]

    def build_analyze_prompt(self):
        products = self.db.get_products()
        batches = self.db.get_active_batches()
        velocity = self.db.get_sales_velocity(days=30)

        from db import get_batch_remaining

        batch_map = {}
        for b in batches:
            slug = b["product_slug"]
            remaining = get_batch_remaining(b)
            batch_map[slug] = {
                "batch_id": b["id"],
                "total": b["units_total"],
                "sold": b["units_sold"],
                "remaining": remaining,
                "cost": b["cost_per_unit_cents"],
                "expires": b["expires_at"][:10],
            }

        products_text = ""
        total_capital = 0
        total_potential = 0

        for p in products:
            batch = batch_map.get(p["slug"], {})
            vel = next((v for v in velocity if v["slug"] == p["slug"]), None)
            units_sold_30d = vel["total_qty"] if vel and vel.get("total_qty") else 0
            daily_rate = units_sold_30d / 30 if units_sold_30d else 0

            stock = p['stock'] + batch.get("remaining", 0)
            days_of_stock = (stock / daily_rate) if daily_rate > 0 else float('inf')

            # ROI calc
            cost = batch.get("cost", 0)
            retail = p['price_cents']
            margin_pct = ((retail - cost) / cost * 100) if cost else 0

            # Streaming capable?
            specs = p.get('specs', '{}')
            has_wifi = 'WiFi' in specs or 'wifi' in specs.lower() or '802.11' in specs
            has_moonlight = 'Moonlight' in specs or 'moonlight' in specs
            streaming = "YES" if (has_wifi and has_moonlight) else ("WiFi only" if has_wifi else "no")

            capital = batch.get("remaining", 0) * cost
            total_capital += capital
            total_potential += batch.get("remaining", 0) * retail

            products_text += (
                f"  {p['name']} ({p['slug']}): "
                f"price=${retail/100:.2f} cost=${cost/100:.2f if cost else '?'} margin={margin_pct:.0f}% "
                f"stock={p['stock']} batch_left={batch.get('remaining',0)} "
                f"30d_sold={units_sold_30d} rate={daily_rate:.2f}/day "
                f"days_of_stock={'%.0f' % days_of_stock if days_of_stock != float('inf') else 'INF'} "
                f"streaming={streaming} "
                f"badge={p.get('badge','')} featured={p.get('featured',0)}\n"
            )

        return f"""Analyze inventory and sales velocity for RetroZone.

For each product, evaluate through our three lenses:

**VELOCITY**: How fast is it selling? What's the reorder point? Fast movers should NEVER stock out.
**ROI**: What's the margin per unit? Which products generate the most return per dollar invested?
**ETHOS**: Are budget options ($50-80) well-stocked? Are streaming-capable devices available? These are our mission-critical products.

Also note:
- Products with WiFi + Moonlight = streaming devices. These serve our "modern gaming for cheap" mission.
- Budget devices (under $60) = gateway products. Always keep these in stock.
- Premium devices can have tighter margins if they drive volume.

Return:
- REORDER NOW (velocity critical): running out within 14 days
- REORDER SOON: running out within 30 days
- HIGH ROI HEROES: best margin products — prioritize reordering these
- MISSION CRITICAL: budget + streaming devices that serve the ethos
- OVERSTOCKED: capital sitting idle
- DEAD STOCK: zero velocity in 30 days — consider clearing
- SUMMARY: total reorder cost, expected ROI, velocity impact

TOTALS: Capital deployed: ${total_capital/100:.2f} | Potential revenue: ${total_potential/100:.2f}

PRODUCTS:
{products_text}"""

    def build_propose_prompt(self, analyze_result):
        return f"""Based on your sales velocity analysis:
{analyze_result}

Propose specific reorder actions. Be CONSERVATIVE with capital — only reorder products with proven demand.

Each action:
- "description": e.g. "Reorder 20x R36S Black at ~$480 AUD"
- "reason": velocity/ROI/ethos justification
- "sql": INSERT INTO inventory_batches with realistic dates (arrives +25 days, expires +90 days)
- "reversible": false (spending money)
- "risk": "high"

Prioritize: 1) mission-critical budget devices, 2) high-velocity high-ROI products, 3) streaming devices.
Return ONLY the JSON array."""
