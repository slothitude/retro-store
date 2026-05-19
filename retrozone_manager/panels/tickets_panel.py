"""Tickets panel — ticket queue with message history."""
import tkinter as tk
from .. import config
from ..db_layer import StoreDB
from ..widgets.data_table import DataTable


class TicketsPanel(tk.Frame):
    def __init__(self, parent, app=None, **kw):
        super().__init__(parent, bg=config.BG_PANEL, **kw)
        self.app = app
        self.db = StoreDB()
        self._build()

    def _build(self):
        header = tk.Frame(self, bg=config.BG_PANEL)
        header.pack(fill="x", padx=20, pady=(15, 10))

        tk.Label(header, text="Support Tickets", font=(config.FONT_FAMILY, config.FONT_SIZE_TITLE, "bold"),
                 bg=config.BG_PANEL, fg=config.FG_PRIMARY).pack(side="left")

        # Filter
        self.filter_var = tk.StringVar(value="all")
        filter_frame = tk.Frame(header, bg=config.BG_PANEL)
        filter_frame.pack(side="right")

        for val, label in [("all", "All"), ("open", "Open"), ("in_progress", "In Progress"),
                           ("resolved", "Resolved"), ("closed", "Closed")]:
            tk.Radiobutton(
                filter_frame, text=label, variable=self.filter_var, value=val,
                command=self.refresh, bg=config.BG_PANEL, fg=config.FG_SECONDARY,
                selectcolor=config.BG_CARD, activebackground=config.BG_PANEL,
                activeforeground=config.FG_PRIMARY, font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                indicatoron=0, bd=1, relief="flat", padx=8, pady=3
            ).pack(side="left", padx=2)

        # Table
        self.table = DataTable(self,
                                columns=["Key", "Subject", "Email", "Category", "Priority", "Status", "Updated"],
                                col_widths=[90, 200, 160, 80, 70, 90, 140])
        self.table.pack(fill="both", expand=True, padx=20, pady=(0, 5))

        # Detail: messages
        self.detail_frame = tk.Frame(self, bg=config.BG_CARD, padx=15, pady=10)
        self.detail_frame.pack(fill="x", padx=20, pady=(0, 10))

        self.detail_label = tk.Label(self.detail_frame, text="Click a ticket to view messages",
                                      font=(config.FONT_FAMILY, config.FONT_SIZE),
                                      bg=config.BG_CARD, fg=config.FG_SECONDARY,
                                      justify="left", wraplength=900)
        self.detail_label.pack(anchor="w")

        self.table.on_select(self._on_ticket_select)
        self.refresh()

    def refresh(self):
        status = self.filter_var.get()
        tickets = self.db.get_tickets(status=status if status != "all" else None)
        self.table.clear()
        for t in tickets:
            self.table.add_row([
                t["ticket_key"], t["subject"], t["email"],
                t.get("category", ""), t.get("priority", ""),
                t["status"], t["updated_at"][:16] if t["updated_at"] else ""
            ])

    def _on_ticket_select(self, row_data):
        if not row_data:
            return
        import json
        ticket = self.db.get_ticket(row_data[0])
        if not ticket:
            return

        messages = json.loads(ticket.get("messages_json", "[]"))
        msg_text = "\n".join(
            f"  [{m.get('time', '?')[:16]}] {m.get('from', '?').title()}: {m.get('text', '')}"
            for m in messages
        ) or "  (no messages)"

        text = (
            f"Ticket {ticket['ticket_key']} — {ticket['subject']}\n"
            f"From: {ticket.get('name', '')} ({ticket['email']})  |  "
            f"Order: {ticket.get('order_ref', '—')}  |  "
            f"Priority: {ticket.get('priority', '—')}  |  Status: {ticket['status']}\n\n"
            f"Messages:\n{msg_text}"
        )
        self.detail_label.configure(text=text)
