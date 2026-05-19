"""Daily Briefing workflow — morning summary, no approval needed."""
from .base import BaseWorkflow


class DailyBriefing(BaseWorkflow):
    name = "Daily Briefing"
    description = "Morning summary report"
    risk_level = "low"

    def get_steps(self):
        return [{
            "name": "Generate Morning Briefing",
            "type": "analyze",
        }]

    def build_analyze_prompt(self):
        summary = self.db.get_store_state_summary()
        orders_24h = self.db.get_orders_since(24)
        active_batches = self.db.get_active_batches()
        all_batches = self.db.get_batches()
        open_tickets = self.db.get_tickets(status="open")
        in_progress_tickets = self.db.get_tickets(status="in_progress")

        # Format orders
        orders_text = "\n".join(
            f"  #{o['id']}: {o['email']} — ${o['total_cents']/100:.2f} [{o['status']}] — {o['created_at'][:16]}"
            for o in orders_24h
        ) or "  (no orders in last 24h)"

        # Format batches with velocity + ROI
        from db import get_batch_phase, get_batch_price, get_batch_remaining
        from datetime import datetime

        batches_text = ""
        for b in active_batches:
            phase = get_batch_phase(b)
            price = get_batch_price(b)
            remaining = get_batch_remaining(b)
            cost = b['cost_per_unit_cents']
            margin_pct = ((price - cost) / cost * 100) if cost else 0

            # Velocity calc
            created = b.get('created_at', b.get('ordered_at', ''))
            try:
                days_active = max(1, (datetime.utcnow() - datetime.fromisoformat(created)).days)
            except (ValueError, TypeError):
                days_active = 1
            daily_vel = b['units_sold'] / days_active if days_active else 0
            days_to_sellout = (remaining / daily_vel) if daily_vel > 0 else float('inf')

            # Capital tied up
            capital_tied = remaining * cost

            batches_text += (
                f"  {b.get('product_name', b['product_slug'])}: "
                f"{b['units_sold']}/{b['units_total']} sold ({remaining} left), "
                f"phase={phase}, price=${price/100:.2f}, cost=${cost/100:.2f}, "
                f"margin={margin_pct:.0f}%, "
                f"velocity={daily_vel:.1f}/day, "
                f"days_to_sellout={'%.0f' % days_to_sellout if days_to_sellout != float('inf') else 'NEVER'}, "
                f"capital_tied=${capital_tied/100:.2f}, "
                f"expires={b['expires_at'][:10]}\n"
            )

        if not batches_text:
            batches_text = "  (no active batches)"

        # Tickets
        all_tickets = open_tickets + in_progress_tickets
        tickets_text = "\n".join(
            f"  {t['ticket_key']}: {t['subject']} [{t['status']}] from {t['email']}"
            for t in all_tickets
        ) or "  (no open tickets)"

        # Total capital deployed
        total_capital = sum(
            get_batch_remaining(b) * b['cost_per_unit_cents']
            for b in active_batches
        )
        total_potential_revenue = sum(
            get_batch_remaining(b) * get_batch_price(b)
            for b in active_batches
        )
        revenue = self.db.get_total_revenue_cents()

        return f"""Generate the RetroZone morning briefing.

Structure it as:

## VELOCITY DASHBOARD
- Units sold today / this week / all-time
- Fastest-moving products
- Stalled inventory (anything with 0 velocity)
- Capital velocity: how fast is money turning over?

## ROI SNAPSHOT
- Revenue earned vs capital deployed
- Margin per active batch
- Capital efficiency ratio (revenue / capital_tied)
- Which products are generating the best return?

## ETHOS CHECK
- Are we keeping gaming affordable? (flag if any price seems like gouging)
- Are budget options ($50-80 range) getting enough visibility?
- Are streaming-capable devices (WiFi + Moonlight) being promoted?
- Any customer complaints about value?

## OVERNIGHT ACTIVITY
- New orders, revenue
- Anything needing immediate attention

## BATCH ALERTS
- Batches running low or expiring soon
- Stalled batches (velocity near zero)
- Clearance candidates

## TICKETS
- Open issues

## ACTION ITEMS
Prioritized list. Tag each as [ROI], [VELOCITY], or [ETHOS].

STORE STATE:
{summary}

ORDERS (last 24h):
{orders_text}

ACTIVE BATCHES:
{batches_text}

TOTALS: Capital deployed: ${total_capital/100:.2f} | Potential revenue remaining: ${total_potential_revenue/100:.2f} | Revenue earned: ${revenue/100:.2f}

OPEN TICKETS:
{tickets_text}"""
