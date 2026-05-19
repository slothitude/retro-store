"""Order Comms workflow — draft customer update emails for shipped orders."""
from .base import BaseWorkflow


class OrderComms(BaseWorkflow):
    name = "Order Comms"
    description = "Send customer update emails"
    risk_level = "high"

    def get_steps(self):
        return [
            {"name": "Find Shipped Orders", "type": "analyze"},
            {"name": "Draft Customer Emails", "type": "research",
             "timeout": 300},
            {"name": "Review Drafts", "type": "propose"},
        ]

    def build_analyze_prompt(self) -> str:
        orders = self.db.get_orders(status="shipped")
        orders_text = "\n".join(
            f"  #{o['id']}: {o['email']} — ${o['total_cents']/100:.2f} "
            f"tracking={o.get('tracking', 'N/A')} items={o.get('items_json', '[]')}"
            for o in orders[:20]
        ) or "  (no shipped orders)"

        return (
            "Identify shipped orders that need customer notification emails.\n\n"
            "SHIPPED ORDERS:\n"
            f"{orders_text}\n\n"
            "For each shipped order, determine:\n"
            "1. Does it have tracking info? If yes, customer should be notified.\n"
            "2. What items were ordered? (parse items_json)\n"
            "3. What's the customer email?\n\n"
            "List the orders that need email notifications, with details for drafting."
        )

    def build_research_prompt(self) -> str:
        return (
            "Based on the shipped orders analysis, draft customer notification emails.\n\n"
            "For each order that needs an email:\n"
            "1. Use draft_email(to, subject, body) to create each email draft\n"
            "2. Subject should be like 'Your RetroZone Order #{id} Has Shipped!'\n"
            "3. Body should include:\n"
            "   - Friendly greeting\n"
            "   - What items shipped\n"
            "   - Tracking number and link (if available)\n"
            "   - Expected delivery estimate\n"
            "   - Thank them for supporting affordable gaming\n"
            "   - Support contact info (support@retrozone.com.au)\n\n"
            "IMPORTANT: Use draft_email for each one. These drafts will be reviewed before sending.\n"
            "Report how many drafts were created."
        )

    def build_propose_prompt(self, analyze_result: str) -> str:
        return (
            f"Review the email drafts created:\n{analyze_result}\n\n"
            "List each draft with its ID, recipient, and subject.\n"
            "Propose which drafts to approve for sending. Each action:\n"
            '- "description": "Send draft email #{id} to {recipient}"\n'
            '- "reason": order context\n'
            '- "draft_id": the draft ID\n'
            '- "reversible": false\n'
            '- "risk": "high"\n\n'
            "Return ONLY the JSON array."
        )

    def execute_action(self, action: dict):
        """Send an approved email draft via SMTP."""
        import smtplib
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from retrozone_manager import config
        from retrozone_manager.mcp_server.db.schema import get_conn

        settings = config.load_settings()
        smtp_host = settings.get("smtp_host", "")
        smtp_port = int(settings.get("smtp_port", 587))
        smtp_user = settings.get("smtp_user", "")
        smtp_pass = settings.get("smtp_password", "")

        if not smtp_host:
            raise ValueError("SMTP not configured. Set smtp_host, smtp_user, smtp_password in Settings.")

        draft_id = action.get("draft_id")
        if not draft_id:
            raise ValueError("No draft_id in action")

        conn = get_conn()
        draft = conn.execute("SELECT * FROM email_drafts WHERE id = ?", (draft_id,)).fetchone()
        if not draft:
            conn.close()
            raise ValueError(f"Draft #{draft_id} not found")

        # Build email
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = draft["to_addr"]
        msg["Subject"] = draft["subject"]
        msg.attach(MIMEText(draft["body"], "plain"))

        # Send
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()

        try:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()

            # Update draft status
            from datetime import datetime
            conn.execute(
                "UPDATE email_drafts SET status = 'sent', sent_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), draft_id)
            )
            conn.commit()
        finally:
            conn.close()
