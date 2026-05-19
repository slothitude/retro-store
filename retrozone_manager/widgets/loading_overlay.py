"""Loading overlay — 'Retro is thinking...' overlay."""
import tkinter as tk
from .. import config


class LoadingOverlay(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=config.BG_DARK, **kw)
        self._build()

    def _build(self):
        # Semi-transparent effect via solid bg
        inner = tk.Frame(self, bg=config.BG_CARD, padx=30, pady=20)
        inner.place(relx=0.5, rely=0.5, anchor="center")

        self.label = tk.Label(inner, text="Retro is thinking...",
                               font=(config.FONT_FAMILY, config.FONT_SIZE_LARGE),
                               bg=config.BG_CARD, fg=config.FG_WARNING)
        self.label.pack()

        self.sub_label = tk.Label(inner, text="",
                                   font=(config.FONT_FAMILY, config.FONT_SIZE),
                                   bg=config.BG_CARD, fg=config.FG_SECONDARY)
        self.sub_label.pack(pady=(5, 0))

    def show(self, message="Retro is thinking...", sub=""):
        self.label.configure(text=message)
        self.sub_label.configure(text=sub)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)

    def hide(self):
        self.place_forget()
