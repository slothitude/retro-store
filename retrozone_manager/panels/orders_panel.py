"""Orders panel — order table with search/filter/detail."""
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

        # Detail panel (collapsible)
        self.detail_frame = tk.Frame(self, bg=config.BG_CARD, padx=15, pady=10)
        self.detail_frame.pack(fill="x", padx=20, pady=(0, 10))

        self.detail_label = tk.Label(self.detail_frame, text="Click an order to view details",
                                      font=(config.FONT_FAMILY, config.FONT_SIZE),
                                      bg=config.BG_CARD, fg=config.FG_SECONDARY, justify="left")
        self.detail_label.pack(anchor="w")

        # Bottom bar
        bottom = tk.Frame(self, bg=config.BG_PANEL)
        bottom.pack(fill="x", padx=20, pady=(0, 10))

        tk.Button(bottom, text="Refresh", command=self.refresh,
                  bg=config.BG_CARD, fg=config.FG_PRIMARY,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=15, pady=5, cursor="hand2").pack(side="right")

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
        order_id = int(row_data[0])
        order = self.db.get_order(order_id)
        if not order:
            return

        import json
        items = json.loads(order.get("items_json", "[]"))
        items_text = "\n".join(
            f"  - {i.get('name', i.get('slug', '?'))} x{i.get('qty', 1)} @ ${i.get('price_cents', 0)/100:.2f}"
            for i in items
        )

        text = (
            f"Order #{order['id']}  |  {order['email']}  |  {order.get('name', '')}\n"
            f"Status: {order['status']}  |  Total: ${order['total_cents']/100:.2f}\n"
            f"Tracking: {order.get('tracking', '—')}\n"
            f"Address: {order.get('address', '—')}\n"
            f"Items:\n{items_text}\n"
            f"Created: {order['created_at']}  |  Updated: {order.get('updated_at', '—')}"
        )
        self.detail_label.configure(text=text)
