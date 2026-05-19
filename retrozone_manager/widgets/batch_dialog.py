"""Batch dialog — modal form for creating an inventory batch."""
import tkinter as tk
from tkinter import messagebox
from datetime import date
from .. import config


class BatchDialog(tk.Toplevel):
    """Modal dialog for creating a new inventory batch."""

    def __init__(self, parent, db):
        super().__init__(parent)
        self.title("New Batch")
        self.geometry("420x380")
        self.configure(bg=config.BG_DARK)
        self.transient(parent)
        self.grab_set()
        self.db = db
        self.result = False

        self._build()
        self.wait_window()

    def _build(self):
        frame = tk.Frame(self, bg=config.BG_DARK, padx=20, pady=15)
        frame.pack(fill="both", expand=True)

        fields = []

        # Product slug combobox
        tk.Label(frame, text="Product:", font=(config.FONT_FAMILY, config.FONT_SIZE),
                 bg=config.BG_DARK, fg=config.FG_SECONDARY).pack(anchor="w", pady=(0, 2))
        products = self.db.get_products()
        product_slugs = [p["slug"] for p in products]

        self.product_var = tk.StringVar()
        self.product_combo = tk.Combobox(frame, textvariable=self.product_var,
                                          values=product_slugs, state="readonly",
                                          font=(config.FONT_FAMILY, config.FONT_SIZE),
                                          bg=config.BG_INPUT, fg=config.FG_PRIMARY)
        self.product_combo.pack(fill="x", pady=(0, 8))
        if product_slugs:
            self.product_combo.current(0)

        # Units total
        tk.Label(frame, text="Units Total:", font=(config.FONT_FAMILY, config.FONT_SIZE),
                 bg=config.BG_DARK, fg=config.FG_SECONDARY).pack(anchor="w", pady=(0, 2))
        self.units_entry = tk.Entry(frame, font=(config.FONT_FAMILY, config.FONT_SIZE),
                                     bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                                     insertbackground=config.FG_PRIMARY, bd=0)
        self.units_entry.pack(fill="x", pady=(0, 8))
        self.units_entry.insert(0, "10")

        # Cost per unit (cents)
        tk.Label(frame, text="Cost per Unit (in cents):", font=(config.FONT_FAMILY, config.FONT_SIZE),
                 bg=config.BG_DARK, fg=config.FG_SECONDARY).pack(anchor="w", pady=(0, 2))
        self.cost_entry = tk.Entry(frame, font=(config.FONT_FAMILY, config.FONT_SIZE),
                                    bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                                    insertbackground=config.FG_PRIMARY, bd=0)
        self.cost_entry.pack(fill="x", pady=(0, 8))
        self.cost_entry.insert(0, "1000")

        today = date.today().isoformat()

        # Dates
        for attr, label, default in [
            ("ordered_at", "Ordered At (YYYY-MM-DD):", today),
            ("arrives_at", "Arrives At (YYYY-MM-DD):", ""),
            ("expires_at", "Expires At (YYYY-MM-DD):", ""),
        ]:
            tk.Label(frame, text=label, font=(config.FONT_FAMILY, config.FONT_SIZE),
                     bg=config.BG_DARK, fg=config.FG_SECONDARY).pack(anchor="w", pady=(0, 2))
            entry = tk.Entry(frame, font=(config.FONT_FAMILY, config.FONT_SIZE),
                             bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                             insertbackground=config.FG_PRIMARY, bd=0)
            entry.pack(fill="x", pady=(0, 8))
            if default:
                entry.insert(0, default)
            setattr(self, f"{attr}_entry", entry)

        # Buttons
        btn_frame = tk.Frame(frame, bg=config.BG_DARK)
        btn_frame.pack(fill="x", pady=(10, 0))

        tk.Button(btn_frame, text="Create", command=self._on_create,
                  bg=config.FG_SUCCESS, fg="#ffffff",
                  font=(config.FONT_FAMILY, config.FONT_SIZE, "bold"),
                  bd=0, padx=20, pady=6, cursor="hand2").pack(side="left")

        tk.Button(btn_frame, text="Cancel", command=self.destroy,
                  bg=config.BG_CARD, fg=config.FG_PRIMARY,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=20, pady=6, cursor="hand2").pack(side="right")

    def _on_create(self):
        product_slug = self.product_var.get().strip()
        if not product_slug:
            messagebox.showwarning("Validation", "Select a product.", parent=self)
            return

        try:
            units = int(self.units_entry.get().strip())
        except ValueError:
            messagebox.showwarning("Validation", "Units must be an integer.", parent=self)
            return

        try:
            cost = int(self.cost_entry.get().strip())
        except ValueError:
            messagebox.showwarning("Validation", "Cost must be an integer (cents).", parent=self)
            return

        ordered = self.ordered_at_entry.get().strip()
        arrives = self.arrives_at_entry.get().strip()
        expires = self.expires_at_entry.get().strip()

        if not arrives or not expires:
            messagebox.showwarning("Validation", "Arrives and Expires dates are required.", parent=self)
            return

        self.db.create_batch(product_slug, units, cost, ordered, arrives, expires)
        self.db.log_activity("batch_created", "batch", "", f"{product_slug} x{units}")
        self.result = True
        self.destroy()
