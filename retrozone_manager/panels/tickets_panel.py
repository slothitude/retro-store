"""Tickets panel — ticket queue with message history, reply, and status change."""
import tkinter as tk
from tkinter import messagebox
from .. import config
from ..db_layer import StoreDB
from ..widgets.data_table import DataTable


class TicketsPanel(tk.Frame):
    def __init__(self, parent, app=None, **kw):
        super().__init__(parent, bg=config.BG_PANEL, **kw)
        self.app = app
        self.db = StoreDB()
        self._selected_ticket_key = None
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

        # Detail frame
        self.detail_frame = tk.Frame(self, bg=config.BG_CARD, padx=15, pady=10)
        self.detail_frame.pack(fill="x", padx=20, pady=(0, 10))

        # Metadata
        self.meta_label = tk.Label(self.detail_frame, text="Click a ticket to view details",
                                    font=(config.FONT_FAMILY, config.FONT_SIZE),
                                    bg=config.BG_CARD, fg=config.FG_SECONDARY,
                                    justify="left", wraplength=900)
        self.meta_label.pack(anchor="w")

        # Message history
        self.msg_label = tk.Label(self.detail_frame, text="",
                                   font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                                   bg=config.BG_CARD, fg=config.FG_PRIMARY,
                                   justify="left", wraplength=900, anchor="nw")
        self.msg_label.pack(anchor="w", pady=(8, 0))

        # Status buttons row
        self.status_frame = tk.Frame(self.detail_frame, bg=config.BG_CARD)
        self.status_frame.pack(anchor="w", pady=(10, 0))

        tk.Label(self.status_frame, text="Status:", font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                 bg=config.BG_CARD, fg=config.FG_SECONDARY).pack(side="left", padx=(0, 5))

        self.status_btns = {}
        for val, label in [("open", "Open"), ("in_progress", "In Progress"),
                           ("resolved", "Resolved"), ("closed", "Closed")]:
            btn = tk.Button(
                self.status_frame, text=label,
                font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                bg=config.BG_INPUT, fg=config.FG_SECONDARY,
                bd=1, relief="flat", padx=8, pady=2, cursor="hand2",
                command=lambda v=val: self._change_status(v)
            )
            btn.pack(side="left", padx=2)
            self.status_btns[val] = btn

        # Reply area
        self.reply_frame = tk.Frame(self.detail_frame, bg=config.BG_CARD)
        self.reply_frame.pack(fill="x", pady=(10, 0))

        tk.Label(self.reply_frame, text="Reply:", font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                 bg=config.BG_CARD, fg=config.FG_SECONDARY).pack(anchor="w")

        self.reply_text = tk.Text(self.reply_frame, height=3,
                                   font=(config.FONT_FAMILY, config.FONT_SIZE),
                                   bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                                   insertbackground=config.FG_PRIMARY, bd=1, relief="flat",
                                   wrap="word")
        self.reply_text.pack(fill="x", pady=(3, 0))

        tk.Button(self.reply_frame, text="Send Reply", command=self._send_reply,
                  bg=config.FG_SUCCESS, fg="#ffffff",
                  font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL, "bold"),
                  bd=0, padx=15, pady=4, cursor="hand2").pack(anchor="e", pady=(5, 0))

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
        self._selected_ticket_key = row_data[0]
        self._load_ticket_detail(row_data[0])

    def _load_ticket_detail(self, ticket_key):
        import json
        ticket = self.db.get_ticket(ticket_key)
        if not ticket:
            return

        # Metadata
        self.meta_label.configure(text=(
            f"Ticket {ticket['ticket_key']} — {ticket['subject']}\n"
            f"From: {ticket.get('name', '')} ({ticket['email']})  |  "
            f"Order: {ticket.get('order_ref', '—')}  |  "
            f"Priority: {ticket.get('priority', '—')}  |  Status: {ticket['status']}"
        ))

        # Messages
        messages = json.loads(ticket.get("messages_json", "[]"))
        msg_lines = []
        for m in messages:
            sender = m.get("from", "?")
            time = m.get("time", "?")[:16]
            text = m.get("text", "")
            msg_lines.append(f"[{time}] {sender.title()}: {text}")
        self.msg_label.configure(text="\n".join(msg_lines) if msg_lines else "(no messages)")

        # Highlight current status button
        current = ticket["status"]
        for val, btn in self.status_btns.items():
            if val == current:
                btn.configure(bg=config.FG_ACCENT, fg="#ffffff")
            else:
                btn.configure(bg=config.BG_INPUT, fg=config.FG_SECONDARY)

    def _change_status(self, new_status):
        if not self._selected_ticket_key:
            return
        self.db.update_ticket_status(self._selected_ticket_key, new_status)
        self.db.log_activity("ticket_status_changed", "ticket", self._selected_ticket_key,
                             f"status → {new_status}")
        self._load_ticket_detail(self._selected_ticket_key)
        self.refresh()

    def _send_reply(self):
        if not self._selected_ticket_key:
            return
        text = self.reply_text.get("1.0", "end").strip()
        if not text:
            return
        self.db.add_ticket_message(self._selected_ticket_key, text, is_admin=1)
        self.db.log_activity("ticket_reply", "ticket", self._selected_ticket_key,
                             f"reply: {text[:80]}")
        self.reply_text.delete("1.0", "end")
        self._load_ticket_detail(self._selected_ticket_key)
