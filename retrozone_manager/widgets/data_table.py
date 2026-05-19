"""Reusable ttk.Treeview with sort/search and CSV export."""
import tkinter as tk
from tkinter import ttk, filedialog
import csv
import os
from .. import config


class DataTable(tk.Frame):
    def __init__(self, parent, columns, col_widths=None, **kw):
        super().__init__(parent, bg=config.BG_PANEL, **kw)
        self.columns = columns
        self.col_widths = col_widths or [100] * len(columns)
        self._select_callback = None
        self._build()

    def _build(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("RZ.Treeview",
                        background=config.BG_CARD,
                        foreground=config.FG_PRIMARY,
                        fieldbackground=config.BG_CARD,
                        borderwidth=0,
                        font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                        rowheight=24)
        style.configure("RZ.Treeview.Heading",
                        background=config.BG_INPUT,
                        foreground=config.FG_SECONDARY,
                        borderwidth=0,
                        font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL, "bold"))
        style.map("RZ.Treeview",
                  background=[("selected", config.FG_ACCENT)],
                  foreground=[("selected", "#ffffff")])

        tree_frame = tk.Frame(self, bg=config.BG_PANEL)
        tree_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(tree_frame, columns=self.columns, show="headings",
                                  style="RZ.Treeview", selectmode="browse")

        for col, width in zip(self.columns, self.col_widths):
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=width, minwidth=40, anchor="w")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def add_row(self, values):
        return self.tree.insert("", "end", values=values)

    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def on_select(self, callback):
        self._select_callback = callback

    def _on_select(self, event):
        if self._select_callback:
            selected = self.tree.selection()
            if selected:
                values = self.tree.item(selected[0], "values")
                self._select_callback(list(values))

    def _sort_by(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        try:
            items.sort(key=lambda t: float(t[0].replace("$", "").replace(",", "")))
        except ValueError:
            items.sort(key=lambda t: t[0].lower())

        for index, (val, k) in enumerate(items):
            self.tree.move(k, "", index)

    def export_csv(self, default_filename="export.csv"):
        """Export all rows to a CSV file via save dialog."""
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=default_filename,
            title="Export to CSV"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.columns)
                for item in self.tree.get_children():
                    values = self.tree.item(item, "values")
                    writer.writerow(values)
            return path
        except Exception as e:
            return None
