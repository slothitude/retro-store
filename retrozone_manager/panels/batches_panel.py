"""Batches panel — batch list with health indicators."""
import tkinter as tk
from .. import config
from ..db_layer import StoreDB
from ..widgets.data_table import DataTable


class BatchesPanel(tk.Frame):
    def __init__(self, parent, app=None, **kw):
        super().__init__(parent, bg=config.BG_PANEL, **kw)
        self.app = app
        self.db = StoreDB()
        self._build()

    def _build(self):
        header = tk.Frame(self, bg=config.BG_PANEL)
        header.pack(fill="x", padx=20, pady=(15, 10))

        tk.Label(header, text="Inventory Batches", font=(config.FONT_FAMILY, config.FONT_SIZE_TITLE, "bold"),
                 bg=config.BG_PANEL, fg=config.FG_PRIMARY).pack(side="left")

        tk.Button(header, text="Refresh", command=self.refresh,
                  bg=config.BG_CARD, fg=config.FG_PRIMARY,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=15, pady=5, cursor="hand2").pack(side="right")

        self.table = DataTable(self,
                                columns=["ID", "Product", "Sold/Total", "Remaining", "Cost/Unit",
                                         "Phase", "Batch Price", "Arrives", "Expires", "Status"],
                                col_widths=[40, 150, 80, 70, 70, 80, 80, 100, 100, 70])
        self.table.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self.refresh()

    def refresh(self):
        batches = self.db.get_batches()
        self.table.clear()

        from db import get_batch_phase, get_batch_price, get_batch_remaining
        for b in batches:
            phase = get_batch_phase(b) if b["status"] == "active" else "—"
            price = get_batch_price(b) if b["status"] == "active" else 0
            remaining = get_batch_remaining(b)
            self.table.add_row([
                str(b["id"]),
                b.get("product_name", b["product_slug"]),
                f"{b['units_sold']}/{b['units_total']}",
                str(remaining),
                f"${b['cost_per_unit_cents']/100:.2f}",
                phase,
                f"${price/100:.2f}" if price else "—",
                b["arrives_at"][:10],
                b["expires_at"][:10],
                b["status"],
            ])
