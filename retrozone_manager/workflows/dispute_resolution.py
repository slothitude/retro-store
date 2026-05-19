"""Dispute Resolution workflow — analyze ticket + order, propose resolution."""
import json
from .base import BaseWorkflow


class DisputeResolution(BaseWorkflow):
    name = "Dispute Resolution"
    description = "Resolve a customer ticket"
    risk_level = "high"

    def __init__(self, ticket_key=None):
        super().__init__()
        self.ticket_key = ticket_key

    def get_steps(self):
        return [
            {"name": "Analyze Dispute", "type": "analyze"},
            {"name": "Propose Resolution", "type": "propose"},
            {"name": "Execute Resolution", "type": "execute"},
        ]

    def build_analyze_prompt(self):
        if not self.ticket_key:
            return "ERROR: No ticket key provided."

        ticket = self.db.get_ticket(self.ticket_key)
        if not ticket:
            return f"ERROR: Ticket {self.ticket_key} not found."

        order = None
        if ticket.get("order_ref"):
            try:
                order_id = int(ticket["order_ref"].lstrip("#"))
                order = self.db.get_order(order_id)
            except (ValueError, TypeError):
                orders = self.db.get_orders(limit=100)
                for o in orders:
                    if str(o["id"]) in ticket["order_ref"]:
                        order = o
                        break

        messages = json.loads(ticket.get("messages_json", "[]"))
        msgs_text = "\n".join(
            f"  [{m.get('time','?')[:16]}] {m.get('from','?').title()}: {m.get('text','')}"
            for m in messages
        ) or "  (no messages)"

        order_text = "No linked order"
        if order:
            items = json.loads(order.get("items_json", "[]"))
            items_text = "\n".join(
                f"  - {i.get('name','?')} x{i.get('qty',1)} @ ${i.get('price_cents',0)/100:.2f}"
                for i in items
            )
            order_text = (
                f"Order #{order['id']}: ${order['total_cents']/100:.2f}, "
                f"status={order['status']}\n{items_text}"
            )

        return f"""Analyze this customer dispute for RetroZone.

Our customer ethos is EVERYONE deserves affordable gaming. We never argue with customers over small amounts — a $60 refund is worth less than a loyal customer telling their mates about us.

Evaluate through three lenses:
1. **ETHOS (PRIMARY)**: Is the customer being treated fairly? Err on their side. Goodwill compounds.
2. **ROI**: What's the cost of resolving vs the cost of a bad review / chargeback / lost repeat business?
3. **VELOCITY**: Is this dispute blocking an order from completing? Resolve fast to keep things moving.

Return:
- COMPLAINT: what happened
- VALIDITY: valid / partially valid / invalid
- CUSTOMER SENTIMENT: how angry are they? (calm / annoyed / furious)
- OPTIONS: resolution options with ROI/ethos/velocity notes
- RECOMMENDATION: specific resolution (lean toward generosity)
- ESTIMATED COST: financial impact

TICKET: {ticket['ticket_key']} — {ticket['subject']}
From: {ticket.get('name','')} ({ticket['email']}) | Priority: {ticket.get('priority','normal')}

Messages:
{msgs_text}

ORDER:
{order_text}"""

    def build_propose_prompt(self, analyze_result):
        return f"""Based on your dispute analysis:
{analyze_result}

Propose specific resolution actions. Remember: customer goodwill > saving a few bucks.

Each action:
- "description": e.g. "Issue full refund of $59.99" or "Send replacement unit"
- "reason": why, referencing ethos/ROI/velocity
- "sql": the SQL to execute
- "reversible": false for refunds
- "risk": "high" for financial actions

NOTE: Stripe refunds must be done manually — include a reminder action.
Include a customer reply message as a separate action.
Return ONLY the JSON array."""
