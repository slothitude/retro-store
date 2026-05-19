"""Suppliers panel — supplier CRUD, orders, price history, email drafts."""
import tkinter as tk
from tkinter import messagebox
from .. import config
from ..db_layer import StoreDB
from ..widgets.scrollable import ScrollableFrame


class SuppliersPanel(tk.Frame):
    def __init__(self, parent, app=None, **kw):
        super().__init__(parent, bg=config.BG_PANEL, **kw)
        self.app = app
        self.db = StoreDB()
        self._selected_supplier_id = None
        self._build()
        self.refresh()

    def _build(self):
        # Header
        header = tk.Frame(self, bg=config.BG_PANEL)
        header.pack(fill="x", padx=20, pady=(15, 10))
        tk.Label(header, text="Suppliers", font=(config.FONT_FAMILY, config.FONT_SIZE_TITLE, "bold"),
                 bg=config.BG_PANEL, fg=config.FG_PRIMARY).pack(side="left")

        self.header_btns = tk.Frame(header, bg=config.BG_PANEL)
        self.header_btns.pack(side="right")

        tk.Button(self.header_btns, text="Refresh", command=self.refresh,
                  bg=config.BG_CARD, fg=config.FG_PRIMARY,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=12, pady=3, cursor="hand2").pack(side="right")

        # Tabs
        tab_frame = tk.Frame(self, bg=config.BG_PANEL)
        tab_frame.pack(fill="x", padx=20, pady=(0, 5))

        self._active_tab = "suppliers"
        self.tab_btns = {}
        for tab_key, tab_label in [("suppliers", "Suppliers"), ("orders", "Orders"),
                                    ("prices", "Price History"), ("drafts", "Email Drafts")]:
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

        # Show/hide supplier action buttons based on tab
        for w in self.header_btns.winfo_children():
            if w.cget("text") in ("Add Supplier", "Edit", "Delete", "Compose"):
                w.destroy()

        if self._active_tab == "suppliers":
            self._show_suppliers()
        elif self._active_tab == "orders":
            self._show_orders()
        elif self._active_tab == "prices":
            self._show_price_history()
        elif self._active_tab == "drafts":
            self._show_drafts()

    def _show_suppliers(self):
        # Add CRUD buttons
        tk.Button(self.header_btns, text="Delete", command=self._delete_supplier,
                  bg=config.FG_DANGER, fg="#ffffff",
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=10, pady=3, cursor="hand2").pack(side="right", padx=2)
        tk.Button(self.header_btns, text="Edit", command=self._edit_supplier,
                  bg=config.BG_CARD, fg=config.FG_PRIMARY,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=10, pady=3, cursor="hand2").pack(side="right", padx=2)
        tk.Button(self.header_btns, text="Add Supplier", command=self._add_supplier,
                  bg=config.FG_SUCCESS, fg="#ffffff",
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=10, pady=3, cursor="hand2").pack(side="right", padx=2)

        rows = self.db.get_suppliers()

        if not rows:
            tk.Label(self.content_frame, text="No suppliers tracked yet.\nRun the Supplier Research workflow to find suppliers.",
                     font=(config.FONT_FAMILY, config.FONT_SIZE),
                     bg=config.BG_PANEL, fg=config.FG_SECONDARY, justify="left").pack(anchor="w", pady=20)
            return

        # Header row
        self._table_header(self.content_frame, ["ID", "Name", "Category", "Contact", "Rating", "Notes"])

        self._supplier_rows = []
        for s in rows:
            row_frame = tk.Frame(self.content_frame, bg=config.BG_CARD, padx=10, pady=6)
            row_frame.pack(fill="x", pady=1)

            # Click binding
            sid = s["id"]
            row_frame.bind("<Button-1>", lambda e, i=sid: self._select_supplier(i))
            row_frame.configure(cursor="hand2")

            stars = "*" * (s["rating"] or 0) if s["rating"] else "-"
            items = [
                str(s["id"]),
                s["name"] or "-",
                s["category"] or "-",
                s["contact_email"] or "-",
                stars,
                (s["notes"] or "-")[:40],
            ]
            labels = []
            for j, val in enumerate(items):
                anchor = "w" if j > 0 else "center"
                width = [4, 20, 12, 25, 6, 30][j]
                lbl = tk.Label(row_frame, text=val, font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                         bg=config.BG_CARD, fg=config.FG_PRIMARY, anchor=anchor,
                         width=width)
                lbl.pack(side="left", padx=(5, 10))
                lbl.bind("<Button-1>", lambda e, i=sid: self._select_supplier(i))
                labels.append(lbl)

            self._supplier_rows.append({"frame": row_frame, "id": sid, "labels": labels})

    def _select_supplier(self, supplier_id):
        self._selected_supplier_id = supplier_id
        # Highlight selected row
        for row in getattr(self, '_supplier_rows', []):
            bg = config.FG_ACCENT if row["id"] == supplier_id else config.BG_CARD
            fg = "#ffffff" if row["id"] == supplier_id else config.FG_PRIMARY
            row["frame"].configure(bg=bg)
            for lbl in row["labels"]:
                lbl.configure(bg=bg, fg=fg)

    def _add_supplier(self):
        from ..widgets.supplier_dialog import SupplierDialog
        dialog = SupplierDialog(self, self.db)
        if dialog.result:
            self.refresh()

    def _edit_supplier(self):
        if not self._selected_supplier_id:
            messagebox.showinfo("Select", "Select a supplier first.", parent=self)
            return
        supplier = self.db.get_supplier(self._selected_supplier_id)
        if not supplier:
            return
        from ..widgets.supplier_dialog import SupplierDialog
        dialog = SupplierDialog(self, self.db, supplier=supplier)
        if dialog.result:
            self.refresh()

    def _delete_supplier(self):
        if not self._selected_supplier_id:
            messagebox.showinfo("Select", "Select a supplier first.", parent=self)
            return
        if not messagebox.askyesno("Confirm", "Delete this supplier?", parent=self):
            return
        self.db.delete_supplier(self._selected_supplier_id)
        self.db.log_activity("supplier_deleted", "supplier", self._selected_supplier_id)
        self._selected_supplier_id = None
        self.refresh()

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

    def _show_price_history(self):
        """Show price check history from automated monitoring."""
        from ..mcp_server.db.schema import get_conn
        import json

        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT pc.*, p.name as product_name "
                "FROM price_checks pc LEFT JOIN products p ON pc.product_slug = p.slug "
                "ORDER BY pc.checked_at DESC LIMIT 100"
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            tk.Label(self.content_frame,
                     text="No price checks recorded yet.\nRun the Price Monitor workflow or price_monitor.py script.",
                     font=(config.FONT_FAMILY, config.FONT_SIZE),
                     bg=config.BG_PANEL, fg=config.FG_SECONDARY, justify="left").pack(anchor="w", pady=20)
            return

        self._table_header(self.content_frame, ["Product", "Source", "eBay Sold Avg", "eBay Active Avg", "Our Price", "Delta", "Checked"])

        for r in rows:
            row_frame = tk.Frame(self.content_frame, bg=config.BG_CARD, padx=10, pady=6)
            row_frame.pack(fill="x", pady=1)

            try:
                data = json.loads(r["results_json"]) if r["results_json"] else {}
            except (json.JSONDecodeError, TypeError):
                data = {}

            sold_avg = data.get("ebay_sold", {}).get("avg_price")
            active_avg = data.get("ebay_active", {}).get("avg_price")
            our_price = data.get("our_price_cents", 0) / 100 if data.get("our_price_cents") else None

            sold_str = f"${sold_avg:.2f}" if sold_avg else "-"
            active_str = f"${active_avg:.2f}" if active_avg else "-"
            our_str = f"${our_price:.2f}" if our_price else "-"

            # Delta: our price vs sold avg
            delta_str = "-"
            delta_color = config.FG_SECONDARY
            if our_price and sold_avg:
                delta_pct = ((our_price - sold_avg) / sold_avg) * 100
                delta_str = f"{delta_pct:+.0f}%"
                if delta_pct > 10:
                    delta_color = config.FG_DANGER  # overpriced
                elif delta_pct < -10:
                    delta_color = config.FG_WARNING  # underpriced
                else:
                    delta_color = config.FG_SUCCESS  # competitive

            product_name = r["product_name"] or r["product_slug"]
            checked = r["checked_at"][:16] if r["checked_at"] else "-"

            items = [
                (product_name[:22], config.FG_PRIMARY, 24),
                (r["source"], config.FG_SECONDARY, 6),
                (sold_str, config.FG_INFO, 12),
                (active_str, config.FG_INFO, 12),
                (our_str, config.FG_PRIMARY, 8),
                (delta_str, delta_color, 6),
                (checked, config.FG_SECONDARY, 16),
            ]

            for val, color, width in items:
                tk.Label(row_frame, text=val, font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                         bg=config.BG_CARD, fg=color, width=width).pack(side="left", padx=(5, 10))

    def _show_drafts(self):
        from ..mcp_server.db.schema import get_conn

        # Add Compose button
        tk.Button(self.header_btns, text="Compose", command=self._compose_email,
                  bg=config.FG_INFO, fg="#ffffff",
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=10, pady=3, cursor="hand2").pack(side="right", padx=2)

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

        self._table_header(self.content_frame, ["ID", "To", "Subject", "Status", "Created", ""])

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

            # Send button for draft-status rows
            if d["status"] == "draft":
                tk.Button(row_frame, text="Send", font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                          bg=config.FG_SUCCESS, fg="#ffffff", bd=0, padx=8, pady=1,
                          cursor="hand2",
                          command=lambda did=d["id"]: self._send_draft(did)).pack(side="right", padx=5)

    def _send_draft(self, draft_id):
        if not messagebox.askyesno("Confirm Send", f"Send draft #{draft_id}?", parent=self):
            return
        from ..mcp_server.tools.email_tools import send_draft
        result = send_draft(draft_id)
        if "Error" in result:
            messagebox.showerror("Send Failed", result, parent=self)
        else:
            self.db.log_activity("email_sent", "draft", draft_id)
            self.refresh()

    def _compose_email(self):
        """Open a simple compose dialog."""
        dialog = tk.Toplevel(self)
        dialog.title("Compose Email")
        dialog.geometry("500x350")
        dialog.configure(bg=config.BG_DARK)
        dialog.transient(self)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=config.BG_DARK, padx=20, pady=15)
        frame.pack(fill="both", expand=True)

        # To
        tk.Label(frame, text="To:", font=(config.FONT_FAMILY, config.FONT_SIZE),
                 bg=config.BG_DARK, fg=config.FG_SECONDARY).pack(anchor="w")
        to_entry = tk.Entry(frame, font=(config.FONT_FAMILY, config.FONT_SIZE),
                            bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                            insertbackground=config.FG_PRIMARY, bd=0)
        to_entry.pack(fill="x", pady=(0, 8))

        # Subject
        tk.Label(frame, text="Subject:", font=(config.FONT_FAMILY, config.FONT_SIZE),
                 bg=config.BG_DARK, fg=config.FG_SECONDARY).pack(anchor="w")
        subj_entry = tk.Entry(frame, font=(config.FONT_FAMILY, config.FONT_SIZE),
                              bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                              insertbackground=config.FG_PRIMARY, bd=0)
        subj_entry.pack(fill="x", pady=(0, 8))

        # Body
        tk.Label(frame, text="Body:", font=(config.FONT_FAMILY, config.FONT_SIZE),
                 bg=config.BG_DARK, fg=config.FG_SECONDARY).pack(anchor="w")
        body_text = tk.Text(frame, height=8, font=(config.FONT_FAMILY, config.FONT_SIZE),
                            bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                            insertbackground=config.FG_PRIMARY, bd=0, wrap="word")
        body_text.pack(fill="both", expand=True, pady=(0, 8))

        def _save_draft():
            to = to_entry.get().strip()
            subj = subj_entry.get().strip()
            body = body_text.get("1.0", "end").strip()
            if not to or not subj:
                return
            from ..mcp_server.tools.email_tools import draft_email
            draft_email(to, subj, body)
            self.db.log_activity("email_draft_created", "draft", "", f"to={to}")
            dialog.destroy()
            self.refresh()

        btn_frame = tk.Frame(frame, bg=config.BG_DARK)
        btn_frame.pack(fill="x")

        tk.Button(btn_frame, text="Save Draft", command=_save_draft,
                  bg=config.FG_SUCCESS, fg="#ffffff",
                  font=(config.FONT_FAMILY, config.FONT_SIZE, "bold"),
                  bd=0, padx=15, pady=5, cursor="hand2").pack(side="left")

        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                  bg=config.BG_CARD, fg=config.FG_PRIMARY,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=15, pady=5, cursor="hand2").pack(side="right")

    def _table_header(self, parent, headers):
        header_frame = tk.Frame(parent, bg=config.BG_INPUT, padx=10, pady=4)
        header_frame.pack(fill="x", pady=(0, 2))
        for h in headers:
            tk.Label(header_frame, text=h, font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL, "bold"),
                     bg=config.BG_INPUT, fg=config.FG_SECONDARY).pack(side="left", padx=(5, 10))
