"""Orders panel — order table with search/filter/detail, status change, tracking edit."""
import tkinter as tk
from tkinter import ttk
from .. import config
from ..db_layer import StoreDB
from ..widgets.data_table import DataTable


class OrdersPanel(tk.Frame):
    def __init__(self, parent, app=None, **kw):
        super().__init__(parent, bg=config.BG_PANEL, **kw)
        self.app = app
        self.db = StoreDB()
        self._selected_order_id = None
        self._build()

    def _build(self):
        # Title row
        header = tk.Frame(self, bg=config.BG_PANEL)
        header.pack(fill="x", padx=20, pady=(15, 10))

        tk.Label(header, text="Orders", font=(config.FONT_FAMILY, config.FONT_SIZE_TITLE, "bold"),
                 bg=config.BG_PANEL, fg=config.FG_PRIMARY).pack(side="left")

        # Filter buttons
        self.filter_var = tk.StringVar(value="all")
        filters = [("all", "All"), ("pending", "Pending"), ("paid", "Paid"),
                   ("shipped", "Shipped"), ("completed", "Done"), ("refunded", "Refunded")]

        filter_frame = tk.Frame(header, bg=config.BG_PANEL)
        filter_frame.pack(side="right")

        for val, label in filters:
            tk.Radiobutton(
                filter_frame, text=label, variable=self.filter_var, value=val,
                command=self.refresh, bg=config.BG_PANEL, fg=config.FG_SECONDARY,
                selectcolor=config.BG_CARD, activebackground=config.BG_PANEL,
                activeforeground=config.FG_PRIMARY, font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                indicatoron=0, bd=1, relief="flat", padx=8, pady=3
            ).pack(side="left", padx=2)

        # Table
        self.table = DataTable(self, columns=["ID", "Email", "Name", "Total", "Status", "Tracking", "Date"],
                                col_widths=[50, 180, 120, 80, 80, 120, 140])
        self.table.pack(fill="both", expand=True, padx=20, pady=(0, 5))

        # Detail panel
        self.detail_frame = tk.Frame(self, bg=config.BG_CARD, padx=15, pady=10)
        self.detail_frame.pack(fill="x", padx=20, pady=(0, 10))

        # Order metadata
        self.detail_label = tk.Label(self.detail_frame, text="Click an order to view details",
                                      font=(config.FONT_FAMILY, config.FONT_SIZE),
                                      bg=config.BG_CARD, fg=config.FG_SECONDARY, justify="left")
        self.detail_label.pack(anchor="w")

        # Status change row
        self.status_frame = tk.Frame(self.detail_frame, bg=config.BG_CARD)
        self.status_frame.pack(anchor="w", pady=(10, 0))

        tk.Label(self.status_frame, text="Status:", font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                 bg=config.BG_CARD, fg=config.FG_SECONDARY).pack(side="left", padx=(0, 5))

        self.status_btns = {}
        for val, label in [("pending", "Pending"), ("paid", "Paid"), ("shipped", "Shipped"),
                           ("completed", "Done"), ("refunded", "Refunded")]:
            btn = tk.Button(
                self.status_frame, text=label,
                font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                bg=config.BG_INPUT, fg=config.FG_SECONDARY,
                bd=1, relief="flat", padx=8, pady=2, cursor="hand2",
                command=lambda v=val: self._change_status(v)
            )
            btn.pack(side="left", padx=2)
            self.status_btns[val] = btn

        # Tracking row
        self.tracking_frame = tk.Frame(self.detail_frame, bg=config.BG_CARD)
        self.tracking_frame.pack(fill="x", pady=(10, 0))

        tk.Label(self.tracking_frame, text="Tracking:", font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                 bg=config.BG_CARD, fg=config.FG_SECONDARY).pack(side="left", padx=(0, 5))

        self.tracking_entry = tk.Entry(self.tracking_frame, width=30,
                                        font=(config.FONT_FAMILY, config.FONT_SIZE),
                                        bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                                        insertbackground=config.FG_PRIMARY, bd=1, relief="flat")
        self.tracking_entry.pack(side="left", padx=(0, 5))

        tk.Button(self.tracking_frame, text="Save Tracking", command=self._save_tracking,
                  bg=config.FG_INFO, fg="#ffffff",
                  font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL, "bold"),
                  bd=0, padx=10, pady=3, cursor="hand2").pack(side="left")

        # Bottom bar
        bottom = tk.Frame(self, bg=config.BG_PANEL)
        bottom.pack(fill="x", padx=20, pady=(0, 10))

        tk.Button(bottom, text="Refresh", command=self.refresh,
                  bg=config.BG_CARD, fg=config.FG_PRIMARY,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=15, pady=5, cursor="hand2").pack(side="right")

        tk.Button(bottom, text="Export CSV", command=self._export_csv,
                  bg=config.BG_CARD, fg=config.FG_SECONDARY,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=15, pady=5, cursor="hand2").pack(side="right", padx=5)

        self.table.on_select(self._on_order_select)
        self.refresh()

    def refresh(self):
        status = self.filter_var.get()
        orders = self.db.get_orders(status=status if status != "all" else None, limit=200)
        self.table.clear()
        for o in orders:
            self.table.add_row([
                str(o["id"]), o["email"], o.get("name", ""),
                f"${o['total_cents']/100:.2f}", o["status"],
                o.get("tracking", "")[:20], o["created_at"][:16] if o["created_at"] else ""
            ])

    def _on_order_select(self, row_data):
        if not row_data:
            return
        self._selected_order_id = int(row_data[0])
        self._load_order_detail(self._selected_order_id)

    def _load_order_detail(self, order_id):
        order = self.db.get_order(order_id)
        if not order:
            return

        import json
        items = json.loads(order.get("items_json", "[]"))
        items_text = "\n".join(
            f"  - {i.get('name', i.get('slug', '?'))} x{i.get('qty', 1)} @ ${i.get('price_cents', 0)/100:.2f}"
            for i in items
        )

        self.detail_label.configure(text=(
            f"Order #{order['id']}  |  {order['email']}  |  {order.get('name', '')}\n"
            f"Status: {order['status']}  |  Total: ${order['total_cents']/100:.2f}  |  "
            f"GST: ${order.get('gst_cents', 0)/100:.2f}\n"
            f"Address: {order.get('address', '—')}\n"
            f"Items:\n{items_text}\n"
            f"Created: {order['created_at']}  |  Updated: {order.get('updated_at', '—')}"
        ))

        # Update tracking entry
        self.tracking_entry.delete(0, "end")
        self.tracking_entry.insert(0, order.get("tracking", ""))

        # Highlight current status button
        current = order["status"]
        for val, btn in self.status_btns.items():
            if val == current:
                btn.configure(bg=config.FG_ACCENT, fg="#ffffff")
            else:
                btn.configure(bg=config.BG_INPUT, fg=config.FG_SECONDARY)

    def _change_status(self, new_status):
        if not self._selected_order_id:
            return
        self.db.update_order_status(self._selected_order_id, new_status)
        self.db.log_activity("order_status_changed", "order", self._selected_order_id,
                             f"status → {new_status}")
        self._load_order_detail(self._selected_order_id)
        self.refresh()

    def _save_tracking(self):
        if not self._selected_order_id:
            return
        tracking = self.tracking_entry.get().strip()
        self.db.update_order_tracking(self._selected_order_id, tracking)
        self.db.log_activity("order_tracking_updated", "order", self._selected_order_id,
                             f"tracking → {tracking}")
        self.refresh()

    def _export_csv(self):
        self.table.export_csv("orders_export.csv")
