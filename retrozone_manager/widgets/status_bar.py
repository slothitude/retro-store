"""Status bar widget at bottom of window."""
import tkinter as tk
from .. import config


class StatusBar(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=config.BG_SIDEBAR, height=28, **kw)
        self.pack_propagate(False)
        self._build()

    def _build(self):
        self.ai_state = tk.Label(
            self, text="AI: IDLE", font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
            bg=config.BG_SIDEBAR, fg=config.FG_SUCCESS, padx=10
        )
        self.ai_state.pack(side="left")

        self.message = tk.Label(
            self, text="Claude ready", font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
            bg=config.BG_SIDEBAR, fg=config.FG_SECONDARY
        )
        self.message.pack(side="left", expand=True)

        self.cost = tk.Label(
            self, text="Session: $0.00", font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
            bg=config.BG_SIDEBAR, fg=config.FG_SECONDARY, padx=10
        )
        self.cost.pack(side="right")

        self.version = tk.Label(
            self, text="v1", font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
            bg=config.BG_SIDEBAR, fg=config.FG_SECONDARY, padx=10
        )
        self.version.pack(side="right")

    def set_state(self, state, msg=""):
        colors = {
            "idle": config.FG_SUCCESS,
            "running": config.FG_WARNING,
            "error": config.FG_DANGER,
            "waiting": config.FG_INFO,
        }
        self.ai_state.configure(text=f"AI: {state.upper()}", fg=colors.get(state, config.FG_PRIMARY))
        if msg:
            self.message.configure(text=msg)

    def add_cost(self, usd):
        current = float(self.cost.cget("text").replace("Session: $", ""))
        self.cost.configure(text=f"Session: ${current + usd:.2f}")

    def reset_session_cost(self):
        self.cost.configure(text="Session: $0.00")
