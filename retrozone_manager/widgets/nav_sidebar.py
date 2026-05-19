"""Navigation sidebar widget."""
import tkinter as tk
from .. import config


class NavSidebar(tk.Frame):
    def __init__(self, parent, on_navigate, **kw):
        super().__init__(parent, bg=config.BG_SIDEBAR, width=160, **kw)
        self.on_navigate = on_navigate
        self.pack_propagate(False)
        self.buttons = {}
        self._build()

    def _build(self):
        # Logo
        logo = tk.Label(self, text="Retro\nZone", font=(config.FONT_FAMILY, 16, "bold"),
                        bg=config.BG_SIDEBAR, fg=config.FG_ACCENT, justify="center")
        logo.pack(pady=(15, 20))

        sep = tk.Frame(self, bg=config.BORDER_COLOR, height=1)
        sep.pack(fill="x", padx=10, pady=(0, 10))

        items = [
            ("dashboard", "Dashboard", "\u2302"),
            ("orders", "Orders", "\u2630"),
            ("batches", "Batches", "\u25A3"),
            ("suppliers", "Suppliers", "\u2603"),
            ("tickets", "Tickets", "\u2709"),
            ("workflows", "Workflows", "\u26A1"),
            ("chat", "Chat", "\u270E"),
            ("settings", "Settings", "\u2699"),
        ]

        for key, label, icon in items:
            btn = tk.Button(
                self, text=f" {icon}  {label}", anchor="w",
                font=(config.FONT_FAMILY, config.FONT_SIZE),
                bg=config.BG_SIDEBAR, fg=config.FG_SECONDARY,
                activebackground=config.BG_CARD, activeforeground=config.FG_PRIMARY,
                bd=0, relief="flat", cursor="hand2", padx=15, pady=8,
                command=lambda k=key: self._navigate(k)
            )
            btn.pack(fill="x")
            self.buttons[key] = btn

        self._highlight("dashboard")

    def _navigate(self, key):
        self._highlight(key)
        self.on_navigate(key)

    def _highlight(self, active_key):
        for key, btn in self.buttons.items():
            if key == active_key:
                btn.configure(bg=config.BG_CARD, fg=config.FG_PRIMARY,
                              font=(config.FONT_FAMILY, config.FONT_SIZE, "bold"))
            else:
                btn.configure(bg=config.BG_SIDEBAR, fg=config.FG_SECONDARY,
                              font=(config.FONT_FAMILY, config.FONT_SIZE))
