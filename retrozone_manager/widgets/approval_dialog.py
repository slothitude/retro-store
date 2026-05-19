"""Approval dialog — modal dialog for human approval with risk levels."""
import tkinter as tk
from .. import config


class ApprovalDialog(tk.Toplevel):
    """Modal dialog showing proposed actions for human approval.

    Risk levels:
      LOW    — "Approve All" button, collapsible details
      MEDIUM — Individual approve/reject per action
      HIGH   — Must type exact confirmation text, red styling
    """

    def __init__(self, parent, actions, risk_level="medium", workflow_name="", step_info=""):
        """
        actions: list of dicts with keys:
            - description: what it does (plain English)
            - reason: why
            - sql: the exact SQL
            - reversible: bool
            - risk: "low"/"medium"/"high" (overrides risk_level per action)
        """
        super().__init__(parent)
        self.result = None  # "approved", "rejected", "modified"
        self.approved_actions = []
        self.actions = actions
        self.risk_level = risk_level
        self.action_vars = []

        self.title("Action Approval Required" if risk_level != "high" else "!! FINANCIAL ACTION — CONFIRM !!")
        self.configure(bg=config.BG_DARK)
        self.geometry("650x500")
        self.transient(parent)
        self.grab_set()

        self._build(workflow_name, step_info)
        self.protocol("WM_DELETE_WINDOW", self._reject)

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self, workflow_name, step_info):
        # Header
        is_high = self.risk_level == "high"
        header_bg = config.FG_DANGER if is_high else config.BG_CARD
        header = tk.Frame(self, bg=header_bg, padx=15, pady=10)
        header.pack(fill="x")

        title = "!! FINANCIAL ACTION — CONFIRM !!" if is_high else "Action Approval Required"
        tk.Label(header, text=title,
                 font=(config.FONT_FAMILY, config.FONT_SIZE_LARGE, "bold"),
                 bg=header_bg, fg="#ffffff" if is_high else config.FG_PRIMARY).pack(anchor="w")

        if workflow_name or step_info:
            tk.Label(header, text=f"{workflow_name} — {step_info}",
                     font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                     bg=header_bg, fg="#ffcccc" if is_high else config.FG_SECONDARY).pack(anchor="w")

        # Scrollable actions
        canvas = tk.Canvas(self, bg=config.BG_PANEL, highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=config.BG_PANEL)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)

        for i, action in enumerate(self.actions):
            risk = action.get("risk", self.risk_level)
            risk_color = config.RISK_COLORS.get(risk, config.FG_PRIMARY)
            self._build_action_card(scroll_frame, i, action, risk, risk_color)

        # Confirmation input (HIGH risk only)
        if is_high:
            confirm_frame = tk.Frame(self, bg=config.BG_DARK, padx=15, pady=10)
            confirm_frame.pack(fill="x")

            confirm_text = self._get_confirm_text()
            tk.Label(confirm_frame, text=f'Type "{confirm_text}" to confirm:',
                     font=(config.FONT_FAMILY, config.FONT_SIZE),
                     bg=config.BG_DARK, fg=config.FG_DANGER).pack(anchor="w")

            self.confirm_entry = tk.Entry(confirm_frame, font=(config.FONT_FAMILY, config.FONT_SIZE),
                                           bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                                           insertbackground=config.FG_PRIMARY, width=50)
            self.confirm_entry.pack(fill="x", pady=(5, 0))
            self.confirm_text = confirm_text

        # Buttons
        btn_frame = tk.Frame(self, bg=config.BG_DARK, padx=15, pady=10)
        btn_frame.pack(fill="x")

        tk.Button(btn_frame, text="Reject All", command=self._reject,
                  bg=config.BG_CARD, fg=config.FG_DANGER,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=15, pady=5, cursor="hand2").pack(side="right", padx=5)

        if self.risk_level == "low":
            tk.Button(btn_frame, text="Approve All", command=self._approve_all,
                      bg=config.FG_SUCCESS, fg="#000000",
                      font=(config.FONT_FAMILY, config.FONT_SIZE, "bold"),
                      bd=0, padx=15, pady=5, cursor="hand2").pack(side="right", padx=5)
        else:
            tk.Button(btn_frame, text="Confirm Approved", command=self._approve_selected,
                      bg=config.BG_CARD, fg=config.FG_PRIMARY,
                      font=(config.FONT_FAMILY, config.FONT_SIZE),
                      bd=0, padx=15, pady=5, cursor="hand2").pack(side="right", padx=5)

    def _build_action_card(self, parent, index, action, risk, risk_color):
        card = tk.Frame(parent, bg=config.BG_CARD, padx=10, pady=8)
        card.pack(fill="x", pady=3)

        # Top row: checkbox + description
        top = tk.Frame(card, bg=config.BG_CARD)
        top.pack(fill="x")

        if self.risk_level != "low":
            var = tk.IntVar(value=0)
            self.action_vars.append((index, var))
            tk.Checkbutton(top, variable=var, bg=config.BG_CARD, fg=config.FG_PRIMARY,
                           selectcolor=config.BG_INPUT, activebackground=config.BG_CARD
                           ).pack(side="left", padx=(0, 8))

        # Risk badge
        tk.Label(top, text=f" {risk.upper()} ", font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL, "bold"),
                 bg=risk_color, fg="#000000", padx=4).pack(side="left", padx=(0, 8))

        tk.Label(top, text=action["description"],
                 font=(config.FONT_FAMILY, config.FONT_SIZE),
                 bg=config.BG_CARD, fg=config.FG_PRIMARY, wraplength=450, justify="left"
                 ).pack(side="left", fill="x", expand=True)

        # Details
        details_frame = tk.Frame(card, bg=config.BG_CARD)
        details_frame.pack(fill="x", padx=(30, 0), pady=(5, 0))

        if action.get("reason"):
            tk.Label(details_frame, text=f"Reason: {action['reason']}",
                     font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                     bg=config.BG_CARD, fg=config.FG_SECONDARY, wraplength=500,
                     justify="left").pack(anchor="w")

        if action.get("sql"):
            tk.Label(details_frame, text=f"SQL: {action['sql']}",
                     font=("Consolas", config.FONT_SIZE_SMALL - 1),
                     bg=config.BG_CARD, fg=config.FG_INFO, wraplength=500,
                     justify="left").pack(anchor="w")

        reversible = "Reversible" if action.get("reversible", False) else "NOT reversible"
        rev_color = config.FG_SUCCESS if action.get("reversible", False) else config.FG_WARNING
        tk.Label(details_frame, text=reversible,
                 font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                 bg=config.BG_CARD, fg=rev_color).pack(anchor="w")

    def _get_confirm_text(self):
        """Generate confirmation text for HIGH risk actions."""
        for a in self.actions:
            desc = a["description"].upper()
            if "REFUND" in desc:
                # Extract dollar amount
                import re
                match = re.search(r'\$[\d,.]+', desc)
                if match:
                    return f"REFUND {match.group()}"
        return "CONFIRM"

    def _approve_all(self):
        self.approved_actions = list(range(len(self.actions)))
        self.result = "approved"
        self.destroy()

    def _approve_selected(self):
        if self.risk_level == "high" and hasattr(self, "confirm_entry"):
            if self.confirm_entry.get().strip() != self.confirm_text:
                self.confirm_entry.configure(bg="#3a1a1a")
                return

        self.approved_actions = [idx for idx, var in self.action_vars if var.get()]
        self.result = "approved"
        self.destroy()

    def _reject(self):
        self.result = "rejected"
        self.destroy()


def show_approval(parent, actions, risk_level="medium", workflow_name="", step_info=""):
    """Show approval dialog and wait. Returns (result, approved_indices)."""
    dialog = ApprovalDialog(parent, actions, risk_level, workflow_name, step_info)
    parent.wait_window(dialog)
    return dialog.result, dialog.approved_actions
