"""ScrollableFrame — drop-in scrollable container for any panel."""
import tkinter as tk
from tkinter import ttk
from .. import config


class ScrollableFrame(tk.Frame):
    """A frame with a vertical scrollbar that wraps any content."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=config.BG_PANEL, **kw)

        # Canvas + scrollbar
        self.canvas = tk.Canvas(self, bg=config.BG_PANEL, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)

        # The actual content frame inside the canvas
        self.scroll_frame = tk.Frame(self.canvas, bg=config.BG_PANEL)

        # Track scroll_frame size and update scrollregion
        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self._window = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")

        # Make scroll_frame fill canvas width
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        self.bind("<Enter>", self._bind_mousewheel)
        self.bind("<Leave>", self._unbind_mousewheel)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._window, width=event.width)

    def _bind_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

    def _unbind_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
