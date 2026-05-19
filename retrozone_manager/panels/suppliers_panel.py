"""Suppliers panel — supplier and order management view."""
import tkinter as tk
from .. import config
from ..widgets.scrollable import ScrollableFrame


class SuppliersPanel(tk.Frame):
    def __init__(self, parent, app=None, **kw):
        super().__init__(parent, bg=config.BG_PANEL, **kw)
        self.app = app
        self._build()
        self.refresh()

    def _build(self):
        # Header
        header = tk.Frame(self, bg=config.BG_PANEL)
        header.pack(fill="x", padx=20, pady=(15, 10))
        tk.Label(header, text="Suppliers", font=(config.FONT_FAMILY, config.FONT_SIZE_TITLE, "bold"),
                 bg=config.BG_PANEL, fg=config.FG_PRIMARY).pack(side="left")
        tk.Button(header, text="Refresh", command=self.refresh,
                  bg=config.BG_CARD, fg=config.FG_PRIMARY,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=12, pady=3, cursor="hand2").pack(side="right")

        # Tabs
        tab_frame = tk.Frame(self, bg=config.BG_PANEL)
        tab_frame.pack(fill="x", padx=20, pady=(0, 5))

        self._active_tab = "suppliers"
        self.tab_btns = {}
        for tab_key, tab_label in [("suppliers", "Suppliers"), ("orders", "Orders"), ("drafts", "Email Drafts")]:
            btn = tk.Button(
                tab_frame, text=tab_label,
                font=(config.FONT_FAMILY, config.FONT_SIZE),
                bg=config.BG_CARD if tab_key == self._active_tab else config.BG_PANEL,
                fg=config.FG_PRIMARY if tab_key == self._active_tab else config.FG_SECONDARY,
                bd=1, relief="flat", padx=15, pady=4, cursor="hand2",
                command=lambda k=tab_key: self._switch_tab(k)
            )
            btn.pack(side="left", padx=(0, 5))
            self.tab_btns[tab_key] = btn

        # Content area
        self.content_frame = tk.Frame(self, bg=config.BG_PANEL)
        self.content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

    def _switch_tab(self, tab_key):
        self._active_tab = tab_key
        for k, btn in self.tab_btns.items():
            if k == tab_key:
                btn.configure(bg=config.BG_CARD, fg=config.FG_PRIMARY)
            else:
                btn.configure(bg=config.BG_PANEL, fg=config.FG_SECONDARY)
        self.refresh()

    def refresh(self):
        # Clear content
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        if self._active_tab == "suppliers":
            self._show_suppliers()
        elif self._active_tab == "orders":
            self._show_orders()
        elif self._active_tab == "drafts":
            self._show_drafts()

    def _show_suppliers(self):
        from ..mcp_server.db.schema import get_conn
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM suppliers ORDER BY name"
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            tk.Label(self.content_frame, text="No suppliers tracked yet.\nRun the Supplier Research workflow to find suppliers.",
                     font=(config.FONT_FAMILY, config.FONT_SIZE),
                     bg=config.BG_PANEL, fg=config.FG_SECONDARY, justify="left").pack(anchor="w", pady=20)
            return

        # Header row
        self._table_header(self.content_frame, ["ID", "Name", "Category", "Contact", "Rating", "Notes"])

        for s in rows:
            row_frame = tk.Frame(self.content_frame, bg=config.BG_CARD, padx=10, pady=6)
            row_frame.pack(fill="x", pady=1)

            stars = "*" * (s["rating"] or 0) if s["rating"] else "-"
            items = [
                str(s["id"]),
                s["name"] or "-",
                s["category"] or "-",
                s["contact_email"] or "-",
                stars,
                (s["notes"] or "-")[:40],
            ]
            for j, val in enumerate(items):
                anchor = "w" if j > 0 else "center"
                width = [4, 20, 12, 25, 6, 30][j]
                tk.Label(row_frame, text=val, font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                         bg=config.BG_CARD, fg=config.FG_PRIMARY, anchor=anchor,
                         width=width).pack(side="left", padx=(5, 10))

    def _show_orders(self):
        from ..mcp_server.db.schema import get_conn
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT o.*, s.name as supplier_name "
                "FROM supplier_orders o JOIN suppliers s ON o.supplier_id = s.id "
                "ORDER BY o.created_at DESC"
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            tk.Label(self.content_frame, text="No supplier orders yet.",
                     font=(config.FONT_FAMILY, config.FONT_SIZE),
                     bg=config.BG_PANEL, fg=config.FG_SECONDARY).pack(anchor="w", pady=20)
            return

        self._table_header(self.content_frame, ["ID", "Supplier", "Product", "Units", "Cost/Unit", "Total", "Status"])

        for o in rows:
            row_frame = tk.Frame(self.content_frame, bg=config.BG_CARD, padx=10, pady=6)
            row_frame.pack(fill="x", pady=1)

            status_color = {
                "pending": config.FG_WARNING,
                "ordered": config.FG_INFO,
                "shipped": config.FG_INFO,
                "received": config.FG_SUCCESS,
                "cancelled": config.FG_DANGER,
            }.get(o["status"], config.FG_PRIMARY)

            items = [
                str(o["id"]),
                o["supplier_name"] or "-",
                o["product_slug"] or "-",
                str(o["units"]),
                f"${o['cost_per_unit_cents']/100:.2f}",
                f"${o['total_cost_cents']/100:.2f}",
            ]
            for j, val in enumerate(items):
                width = [4, 16, 14, 6, 8, 8, 10][j]
                tk.Label(row_frame, text=val, font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                         bg=config.BG_CARD, fg=config.FG_PRIMARY,
                         width=width).pack(side="left", padx=(5, 10))

            tk.Label(row_frame, text=o["status"], font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL, "bold"),
                     bg=config.BG_CARD, fg=status_color).pack(side="left", padx=(5, 10))

    def _show_drafts(self):
        from ..mcp_server.db.schema import get_conn
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM email_drafts ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            tk.Label(self.content_frame, text="No email drafts yet.",
                     font=(config.FONT_FAMILY, config.FONT_SIZE),
                     bg=config.BG_PANEL, fg=config.FG_SECONDARY).pack(anchor="w", pady=20)
            return

        self._table_header(self.content_frame, ["ID", "To", "Subject", "Status", "Created"])

        for d in rows:
            row_frame = tk.Frame(self.content_frame, bg=config.BG_CARD, padx=10, pady=6)
            row_frame.pack(fill="x", pady=1)

            status_color = {
                "draft": config.FG_WARNING,
                "sent": config.FG_SUCCESS,
                "cancelled": config.FG_DANGER,
            }.get(d["status"], config.FG_PRIMARY)

            items = [
                str(d["id"]),
                d["to_addr"],
                (d["subject"] or "")[:35],
                d["status"],
                d["created_at"][:16] if d["created_at"] else "-",
            ]
            colors = [config.FG_PRIMARY, config.FG_PRIMARY, config.FG_PRIMARY, status_color, config.FG_SECONDARY]

            for j, val in enumerate(items):
                width = [4, 25, 30, 8, 16][j]
                tk.Label(row_frame, text=val, font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                         bg=config.BG_CARD, fg=colors[j],
                         width=width).pack(side="left", padx=(5, 10))

    def _table_header(self, parent, headers):
        header_frame = tk.Frame(parent, bg=config.BG_INPUT, padx=10, pady=4)
        header_frame.pack(fill="x", pady=(0, 2))
        for h in headers:
            tk.Label(header_frame, text=h, font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL, "bold"),
                     bg=config.BG_INPUT, fg=config.FG_SECONDARY).pack(side="left", padx=(5, 10))
