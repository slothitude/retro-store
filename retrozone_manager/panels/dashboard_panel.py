"""Dashboard panel — stats cards, recent orders, batch summary, activity log."""
import tkinter as tk
from tkinter import ttk
from .. import config
from ..db_layer import StoreDB
from ..widgets.data_table import DataTable


class DashboardPanel(tk.Frame):
    def __init__(self, parent, app=None, **kw):
        super().__init__(parent, bg=config.BG_PANEL, **kw)
        self.app = app
        self.db = StoreDB()
        self._build()

    def _build(self):
        # Title
        tk.Label(self, text="Dashboard", font=(config.FONT_FAMILY, config.FONT_SIZE_TITLE, "bold"),
                 bg=config.BG_PANEL, fg=config.FG_PRIMARY).pack(anchor="w", padx=20, pady=(15, 10))

        # Stats row
        stats_frame = tk.Frame(self, bg=config.BG_PANEL)
        stats_frame.pack(fill="x", padx=20, pady=(0, 15))

        self.stat_cards = {}
        for key, label in [("orders", "Orders"), ("revenue", "Revenue"),
                           ("tickets", "Tickets"), ("products", "Products")]:
            card = tk.Frame(stats_frame, bg=config.BG_CARD, padx=15, pady=10)
            card.pack(side="left", expand=True, fill="both", padx=(0, 10))
            tk.Label(card, text=label, font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                     bg=config.BG_CARD, fg=config.FG_SECONDARY).pack(anchor="w")
            val_label = tk.Label(card, text="—", font=(config.FONT_FAMILY, config.FONT_SIZE_LARGE, "bold"),
                                 bg=config.BG_CARD, fg=config.FG_PRIMARY)
            val_label.pack(anchor="w")
            self.stat_cards[key] = val_label

        # Two columns below
        cols = tk.Frame(self, bg=config.BG_PANEL)
        cols.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        # Left: Recent orders
        left = tk.Frame(cols, bg=config.BG_PANEL)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        tk.Label(left, text="Recent Orders", font=(config.FONT_FAMILY, config.FONT_SIZE, "bold"),
                 bg=config.BG_PANEL, fg=config.FG_PRIMARY).pack(anchor="w", pady=(0, 5))

        self.orders_table = DataTable(left, columns=["ID", "Email", "Total", "Status", "Date"],
                                       col_widths=[50, 180, 80, 80, 140])
        self.orders_table.pack(fill="both", expand=True)

        # Right: Active Batches
        right = tk.Frame(cols, bg=config.BG_PANEL)
        right.pack(side="left", fill="both", expand=True)

        tk.Label(right, text="Active Batches", font=(config.FONT_FAMILY, config.FONT_SIZE, "bold"),
                 bg=config.BG_PANEL, fg=config.FG_PRIMARY).pack(anchor="w", pady=(0, 5))

        self.batches_table = DataTable(right, columns=["Product", "Sold", "Remaining", "Phase", "Price"],
                                        col_widths=[150, 60, 80, 80, 80])
        self.batches_table.pack(fill="both", expand=True)

        # Refresh button
        btn_frame = tk.Frame(self, bg=config.BG_PANEL)
        btn_frame.pack(fill="x", padx=20, pady=(0, 10))
        tk.Button(btn_frame, text="Refresh", command=self.refresh,
                  bg=config.BG_CARD, fg=config.FG_PRIMARY,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=15, pady=5, cursor="hand2").pack(side="right")
        tk.Button(btn_frame, text="Export Activity", command=lambda: self.activity_table.export_csv("activity_log.csv"),
                  bg=config.BG_CARD, fg=config.FG_SECONDARY,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=15, pady=5, cursor="hand2").pack(side="right", padx=5)

        # Activity log section
        tk.Label(self, text="Recent Activity", font=(config.FONT_FAMILY, config.FONT_SIZE, "bold"),
                 bg=config.BG_PANEL, fg=config.FG_PRIMARY).pack(anchor="w", padx=20, pady=(0, 5))

        self.activity_table = DataTable(self, columns=["Time", "Action", "Target", "Details"],
                                         col_widths=[140, 160, 160, 400])
        self.activity_table.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.refresh()

    def refresh(self):
        try:
            # Auto-expire batches
            self.db.check_batch_expiry()

            total = self.db.get_order_count()
            pending = self.db.get_order_count_by_status("pending")
            paid = self.db.get_order_count_by_status("paid")
            self.stat_cards["orders"].configure(text=f"{total} ({pending} pending, {paid} paid)")

            revenue = self.db.get_total_revenue_cents()
            self.stat_cards["revenue"].configure(text=f"${revenue/100:.2f}")

            tickets = self.db.get_open_ticket_count()
            self.stat_cards["tickets"].configure(text=str(tickets))

            products = self.db.get_product_count()
            self.stat_cards["products"].configure(text=str(products))

            # Recent orders
            orders = self.db.get_recent_orders(10)
            self.orders_table.clear()
            for o in orders:
                self.orders_table.add_row([
                    str(o["id"]), o["email"],
                    f"${o['total_cents']/100:.2f}",
                    o["status"],
                    o["created_at"][:16] if o["created_at"] else ""
                ])

            # Active batches
            from db import get_batch_phase, get_batch_price, get_batch_remaining
            batches = self.db.get_active_batches()
            self.batches_table.clear()
            for b in batches:
                phase = get_batch_phase(b)
                price = get_batch_price(b)
                remaining = get_batch_remaining(b)
                self.batches_table.add_row([
                    b.get("product_name", b["product_slug"]),
                    f"{b['units_sold']}/{b['units_total']}",
                    str(remaining),
                    phase,
                    f"${price/100:.2f}"
                ])

            # Activity log
            activities = self.db.get_activity_log(20)
            self.activity_table.clear()
            for a in activities:
                self.activity_table.add_row([
                    a["created_at"][:16] if a["created_at"] else "",
                    a["action"],
                    f"{a['target_type']} {a['target_id']}".strip(),
                    (a["details"] or "")[:60],
                ])

        except Exception as e:
            self.stat_cards["orders"].configure(text=f"Error: {e}")
