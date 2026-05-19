"""Email compose/approval dialog widget."""
import tkinter as tk
from tkinter import simpledialog
from .. import config


class EmailComposeDialog(tk.Toplevel):
    """Modal dialog for reviewing and approving email drafts."""

    def __init__(self, parent, drafts: list[dict], on_approve=None, on_reject=None):
        super().__init__(parent)
        self.title("Review Email Drafts")
        self.geometry("600x500")
        self.configure(bg=config.BG_DARK)
        self.transient(parent)
        self.grab_set()

        self.drafts = drafts
        self.on_approve = on_approve
        self.on_reject = on_reject
        self.approved_ids = []

        self._build()

    def _build(self):
        # Header
        tk.Label(self, text=f"{len(self.drafts)} Email Draft(s) to Review",
                 font=(config.FONT_FAMILY, config.FONT_SIZE_LARGE, "bold"),
                 bg=config.BG_DARK, fg=config.FG_PRIMARY).pack(pady=(15, 10))

        # Draft list
        container = tk.Frame(self, bg=config.BG_DARK)
        container.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self.check_vars = {}
        for draft in self.drafts:
            var = tk.BooleanVar(value=True)
            self.check_vars[draft["id"]] = var

            frame = tk.Frame(container, bg=config.BG_CARD, padx=12, pady=8)
            frame.pack(fill="x", pady=3)

            cb = tk.Checkbutton(
                frame, variable=var,
                bg=config.BG_CARD, fg=config.FG_PRIMARY,
                selectcolor=config.BG_INPUT,
                activebackground=config.BG_CARD,
                font=(config.FONT_FAMILY, config.FONT_SIZE),
            )
            cb.pack(side="left")

            info = tk.Frame(frame, bg=config.BG_CARD)
            info.pack(side="left", fill="x", expand=True, padx=(10, 0))

            tk.Label(info, text=f"To: {draft['to_addr']}",
                     font=(config.FONT_FAMILY, config.FONT_SIZE),
                     bg=config.BG_CARD, fg=config.FG_PRIMARY).pack(anchor="w")
            tk.Label(info, text=f"Subject: {draft['subject']}",
                     font=(config.FONT_FAMILY, config.FONT_SIZE),
                     bg=config.BG_CARD, fg=config.FG_INFO).pack(anchor="w")
            tk.Label(info, text=draft["body"][:100] + ("..." if len(draft["body"]) > 100 else ""),
                     font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                     bg=config.BG_CARD, fg=config.FG_SECONDARY, wraplength=450,
                     justify="left").pack(anchor="w")

        # Buttons
        btn_frame = tk.Frame(self, bg=config.BG_DARK)
        btn_frame.pack(fill="x", padx=20, pady=(0, 15))

        tk.Button(btn_frame, text="Approve & Send", command=self._approve,
                  bg=config.FG_SUCCESS, fg="#ffffff",
                  font=(config.FONT_FAMILY, config.FONT_SIZE, "bold"),
                  bd=0, padx=20, pady=8, cursor="hand2").pack(side="left", padx=5)

        tk.Button(btn_frame, text="Reject All", command=self._reject,
                  bg=config.FG_DANGER, fg="#ffffff",
                  font=(config.FONT_FAMILY, config.FONT_SIZE, "bold"),
                  bd=0, padx=20, pady=8, cursor="hand2").pack(side="right", padx=5)

    def _approve(self):
        self.approved_ids = [did for did, var in self.check_vars.items() if var.get()]
        self.destroy()
        if self.on_approve:
            self.on_approve(self.approved_ids)

    def _reject(self):
        self.destroy()
        if self.on_reject:
            self.on_reject()
