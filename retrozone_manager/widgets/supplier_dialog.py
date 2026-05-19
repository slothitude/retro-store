"""Supplier dialog — modal form for adding/editing a supplier."""
import tkinter as tk
from .. import config


class SupplierDialog(tk.Toplevel):
    """Modal dialog for creating or editing a supplier."""

    def __init__(self, parent, db, supplier=None):
        super().__init__(parent)
        self.title("Edit Supplier" if supplier else "Add Supplier")
        self.geometry("440x420")
        self.configure(bg=config.BG_DARK)
        self.transient(parent)
        self.grab_set()
        self.db = db
        self.supplier = supplier
        self.result = False

        self._build()
        if supplier:
            self._populate(supplier)
        self.wait_window()

    def _build(self):
        frame = tk.Frame(self, bg=config.BG_DARK, padx=20, pady=15)
        frame.pack(fill="both", expand=True)

        self.entries = {}

        # Name
        tk.Label(frame, text="Name *:", font=(config.FONT_FAMILY, config.FONT_SIZE),
                 bg=config.BG_DARK, fg=config.FG_SECONDARY).pack(anchor="w", pady=(0, 2))
        name_entry = tk.Entry(frame, font=(config.FONT_FAMILY, config.FONT_SIZE),
                              bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                              insertbackground=config.FG_PRIMARY, bd=0)
        name_entry.pack(fill="x", pady=(0, 8))
        self.entries["name"] = name_entry

        # URL
        tk.Label(frame, text="URL:", font=(config.FONT_FAMILY, config.FONT_SIZE),
                 bg=config.BG_DARK, fg=config.FG_SECONDARY).pack(anchor="w", pady=(0, 2))
        url_entry = tk.Entry(frame, font=(config.FONT_FAMILY, config.FONT_SIZE),
                             bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                             insertbackground=config.FG_PRIMARY, bd=0)
        url_entry.pack(fill="x", pady=(0, 8))
        self.entries["url"] = url_entry

        # Contact Email
        tk.Label(frame, text="Contact Email:", font=(config.FONT_FAMILY, config.FONT_SIZE),
                 bg=config.BG_DARK, fg=config.FG_SECONDARY).pack(anchor="w", pady=(0, 2))
        email_entry = tk.Entry(frame, font=(config.FONT_FAMILY, config.FONT_SIZE),
                               bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                               insertbackground=config.FG_PRIMARY, bd=0)
        email_entry.pack(fill="x", pady=(0, 8))
        self.entries["contact_email"] = email_entry

        # Category
        tk.Label(frame, text="Category:", font=(config.FONT_FAMILY, config.FONT_SIZE),
                 bg=config.BG_DARK, fg=config.FG_SECONDARY).pack(anchor="w", pady=(0, 2))
        cat_entry = tk.Entry(frame, font=(config.FONT_FAMILY, config.FONT_SIZE),
                             bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                             insertbackground=config.FG_PRIMARY, bd=0)
        cat_entry.pack(fill="x", pady=(0, 8))
        self.entries["category"] = cat_entry

        # Rating
        tk.Label(frame, text="Rating (0-5):", font=(config.FONT_FAMILY, config.FONT_SIZE),
                 bg=config.BG_DARK, fg=config.FG_SECONDARY).pack(anchor="w", pady=(0, 2))
        self.rating_var = tk.IntVar(value=0)
        rating_spin = tk.Spinbox(frame, from_=0, to=5, textvariable=self.rating_var,
                                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                                  bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                                  buttonbackground=config.BG_INPUT, width=5)
        rating_spin.pack(anchor="w", pady=(0, 8))

        # Notes
        tk.Label(frame, text="Notes:", font=(config.FONT_FAMILY, config.FONT_SIZE),
                 bg=config.BG_DARK, fg=config.FG_SECONDARY).pack(anchor="w", pady=(0, 2))
        notes_text = tk.Text(frame, height=3, font=(config.FONT_FAMILY, config.FONT_SIZE),
                             bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                             insertbackground=config.FG_PRIMARY, bd=0, wrap="word")
        notes_text.pack(fill="x", pady=(0, 8))
        self.entries["notes"] = notes_text

        # Buttons
        btn_frame = tk.Frame(frame, bg=config.BG_DARK)
        btn_frame.pack(fill="x", pady=(10, 0))

        tk.Button(btn_frame, text="Save", command=self._on_save,
                  bg=config.FG_SUCCESS, fg="#ffffff",
                  font=(config.FONT_FAMILY, config.FONT_SIZE, "bold"),
                  bd=0, padx=20, pady=6, cursor="hand2").pack(side="left")

        tk.Button(btn_frame, text="Cancel", command=self.destroy,
                  bg=config.BG_CARD, fg=config.FG_PRIMARY,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=20, pady=6, cursor="hand2").pack(side="right")

    def _populate(self, supplier):
        self.entries["name"].insert(0, supplier.get("name", ""))
        self.entries["url"].insert(0, supplier.get("url", ""))
        self.entries["contact_email"].insert(0, supplier.get("contact_email", ""))
        self.entries["category"].insert(0, supplier.get("category", ""))
        self.rating_var.set(supplier.get("rating", 0))
        self.entries["notes"].insert("1.0", supplier.get("notes", ""))

    def _on_save(self):
        name = self.entries["name"].get().strip()
        if not name:
            return

        fields = {
            "name": name,
            "url": self.entries["url"].get().strip(),
            "contact_email": self.entries["contact_email"].get().strip(),
            "category": self.entries["category"].get().strip(),
            "rating": self.rating_var.get(),
            "notes": self.entries["notes"].get("1.0", "end").strip(),
        }

        if self.supplier:
            self.db.update_supplier(self.supplier["id"], **fields)
            self.db.log_activity("supplier_updated", "supplier", self.supplier["id"],
                                 f"name={name}")
        else:
            sid = self.db.create_supplier(**fields)
            self.db.log_activity("supplier_created", "supplier", sid, f"name={name}")

        self.result = True
        self.destroy()
