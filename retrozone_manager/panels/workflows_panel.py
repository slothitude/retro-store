"""Workflows panel — workflow launcher, progress, reports."""
import tkinter as tk
from .. import config
from ..workflow_engine import WorkflowEngine, StepState
from ..widgets.loading_overlay import LoadingOverlay
from ..widgets.approval_dialog import show_approval


class WorkflowsPanel(tk.Frame):
    def __init__(self, parent, app=None, **kw):
        super().__init__(parent, bg=config.BG_PANEL, **kw)
        self.app = app
        self.engine = WorkflowEngine(app)
        self.engine.set_callbacks(
            on_update=self._on_workflow_update,
            on_approval_needed=self._on_approval_needed,
            on_complete=self._on_workflow_complete,
        )
        self._last_report = ""
        self._build()

    def _build(self):
        # Title
        header = tk.Frame(self, bg=config.BG_PANEL)
        header.pack(fill="x", padx=20, pady=(15, 10))
        tk.Label(header, text="Workflows", font=(config.FONT_FAMILY, config.FONT_SIZE_TITLE, "bold"),
                 bg=config.BG_PANEL, fg=config.FG_PRIMARY).pack(side="left")

        # Workflow cards
        cards_frame = tk.Frame(self, bg=config.BG_PANEL)
        cards_frame.pack(fill="x", padx=20, pady=(0, 15))

        self.workflow_cards = {}
        workflows = [
            ("daily_briefing", "Daily Briefing", "Morning summary report", "low"),
            ("order_review", "Order Review", "Review new orders, flag risky", "low"),
            ("batch_health", "Batch Health Check", "Sell-through analysis", "medium"),
            ("dispute_resolution", "Dispute Resolution", "Resolve a customer ticket", "high"),
            ("reorder", "Reorder Recommend.", "Sales velocity + reorder math", "high"),
            ("supplier_research", "Supplier Research", "Find + compare suppliers on Alibaba", "medium"),
            ("price_monitor", "Price Monitor", "Check competitor eBay pricing", "low"),
            ("order_comms", "Order Comms", "Send customer update emails", "high"),
        ]

        for key, name, desc, risk in workflows:
            card = tk.Frame(cards_frame, bg=config.BG_CARD, padx=15, pady=10)
            card.pack(fill="x", pady=3)

            left = tk.Frame(card, bg=config.BG_CARD)
            left.pack(side="left", fill="x", expand=True)

            risk_color = config.RISK_COLORS.get(risk, config.FG_SECONDARY)
            tk.Label(left, text=name, font=(config.FONT_FAMILY, config.FONT_SIZE, "bold"),
                     bg=config.BG_CARD, fg=config.FG_PRIMARY).pack(anchor="w")
            tk.Label(left, text=desc, font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                     bg=config.BG_CARD, fg=config.FG_SECONDARY).pack(anchor="w")

            right = tk.Frame(card, bg=config.BG_CARD)
            right.pack(side="right")

            # Ticket input for dispute resolution
            if key == "dispute_resolution":
                tk.Label(right, text="Ticket:", font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                         bg=config.BG_CARD, fg=config.FG_SECONDARY).pack(side="left", padx=(0, 5))
                self.ticket_entry = tk.Entry(right, width=12,
                                              font=(config.FONT_FAMILY, config.FONT_SIZE),
                                              bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                                              insertbackground=config.FG_PRIMARY)
                self.ticket_entry.pack(side="left", padx=(0, 10))
                self.ticket_entry.insert(0, "TK-")

            # Product input for supplier research and price monitor
            if key in ("supplier_research", "price_monitor"):
                tk.Label(right, text="Product:", font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                         bg=config.BG_CARD, fg=config.FG_SECONDARY).pack(side="left", padx=(0, 5))
                entry = tk.Entry(right, width=16,
                                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                                  bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                                  insertbackground=config.FG_PRIMARY)
                entry.pack(side="left", padx=(0, 10))
                entry.insert(0, "R36S handheld")
                if not hasattr(self, '_product_entries'):
                    self._product_entries = {}
                self._product_entries[key] = entry

            run_btn = tk.Button(right, text="Run Now",
                                 bg=config.BG_CARD, fg=config.FG_PRIMARY,
                                 font=(config.FONT_FAMILY, config.FONT_SIZE),
                                 bd=1, relief="solid", padx=15, pady=3,
                                 cursor="hand2",
                                 command=lambda k=key: self._run_workflow(k))
            run_btn.pack(side="right")

            self.workflow_cards[key] = {"card": card, "button": run_btn}

        # Progress section
        self.progress_frame = tk.Frame(self, bg=config.BG_PANEL)
        self.progress_frame.pack(fill="x", padx=20, pady=(0, 5))

        self.progress_label = tk.Label(self.progress_frame, text="",
                                        font=(config.FONT_FAMILY, config.FONT_SIZE),
                                        bg=config.BG_PANEL, fg=config.FG_SECONDARY)
        self.progress_label.pack(anchor="w")

        self.progress_bar = tk.Canvas(self.progress_frame, height=8, bg=config.BG_INPUT,
                                       highlightthickness=0)
        self.progress_bar.pack(fill="x", pady=(5, 0))

        # Report section
        report_frame = tk.Frame(self, bg=config.BG_PANEL)
        report_frame.pack(fill="both", expand=True, padx=20, pady=(10, 15))

        self.report_label = tk.Label(report_frame, text="Run a workflow to see results here.",
                                      font=(config.FONT_FAMILY, config.FONT_SIZE),
                                      bg=config.BG_PANEL, fg=config.FG_SECONDARY,
                                      justify="left", wraplength=900, anchor="nw")
        self.report_label.pack(fill="both", expand=True, anchor="nw")

        # Loading overlay
        self.loading = LoadingOverlay(self)

    def _run_workflow(self, key):
        if self.engine.current_run and self.engine.current_run.state in (
            StepState.RUNNING, StepState.WAITING_APPROVAL
        ):
            return  # already running

        workflow_map = {
            "daily_briefing": "daily_briefing.DailyBriefing",
            "order_review": "order_review.OrderReview",
            "batch_health": "batch_health.BatchHealth",
            "dispute_resolution": "dispute_resolution.DisputeResolution",
            "reorder": "reorder_recommendation.ReorderRecommendation",
            "supplier_research": "supplier_research.SupplierResearch",
            "price_monitor": "price_monitor.PriceMonitor",
            "order_comms": "order_comms.OrderComms",
        }

        import importlib
        module_name, class_name = workflow_map[key].rsplit(".", 1)
        module = importlib.import_module(f"retrozone_manager.workflows.{module_name}")
        workflow_cls = getattr(module, class_name)

        # Special handling for dispute resolution (needs ticket key)
        if key == "dispute_resolution":
            ticket_key = self.ticket_entry.get().strip()
            if not ticket_key or ticket_key == "TK-":
                self.report_label.configure(text="Please enter a ticket key (e.g. TK-AB12CD)",
                                             fg=config.FG_WARNING)
                return
            workflow = workflow_cls(ticket_key=ticket_key)

        # Special handling for supplier research and price monitor (need product query)
        elif key in ("supplier_research", "price_monitor"):
            product_query = ""
            if hasattr(self, '_product_entries') and key in self._product_entries:
                product_query = self._product_entries[key].get().strip()
            if not product_query:
                self.report_label.configure(text="Please enter a product to search for (e.g. 'R36S handheld')",
                                             fg=config.FG_WARNING)
                return
            workflow = workflow_cls(product_query=product_query)

        else:
            workflow = workflow_cls()

        self.loading.show(f"Running {workflow.name}...", "Step 1")
        self.app.set_status("running", f"Running {workflow.name}")
        self.engine.run_workflow(workflow)

    def _on_workflow_update(self, run):
        if not run:
            return

        current = run.current_step
        total = len(run.steps)
        state = run.step_states.get(current, "pending")
        step_name = run.steps[current] if current < len(run.steps) else "Done"

        # Update progress
        if run.state == StepState.RUNNING:
            self.progress_label.configure(
                text=f"Running: {run.workflow_name} — Step {current+1}/{total} {step_name} ({state})",
                fg=config.FG_WARNING
            )
            # Progress bar
            self.progress_bar.delete("all")
            pct = (current + 0.5) / total
            w = self.progress_bar.winfo_width()
            self.progress_bar.create_rectangle(0, 0, int(w * pct), 8,
                                                fill=config.FG_WARNING, outline="")

            self.loading.show(f"Running {run.workflow_name}...",
                              f"Step {current+1}/{total}: {step_name}")
            self.app.set_status("running", f"{run.workflow_name}: {step_name}")

        elif run.state == StepState.WAITING_APPROVAL:
            self.progress_label.configure(
                text=f"Waiting approval: {run.workflow_name} — {step_name}",
                fg=config.FG_INFO
            )
            self.loading.hide()
            self.app.set_status("waiting", f"{run.workflow_name}: needs approval")

        elif run.state == StepState.COMPLETED:
            self._show_complete(run)

        elif run.state == StepState.ERROR:
            self.progress_label.configure(
                text=f"Error: {run.error}", fg=config.FG_DANGER
            )
            self.loading.hide()
            self.app.set_status("error", f"Error: {run.error}")

    def _on_approval_needed(self, run, proposals):
        """Called when workflow needs human approval."""
        self.loading.hide()

        risk = self.engine._current_workflow.risk_level
        result, approved = show_approval(
            self.app, proposals,
            risk_level=risk,
            workflow_name=run.workflow_name,
            step_info=f"Step {run.current_step+1}/{len(run.steps)}"
        )

        if result == "approved":
            self.engine.approve(approved)
        else:
            self.engine.reject()

    def _on_workflow_complete(self, run):
        self._show_complete(run)

    def _show_complete(self, run):
        # Collect all results
        report_parts = []
        for idx, step_name in enumerate(run.steps):
            result = run.step_results.get(idx, "")
            state = run.step_states.get(idx, "?")
            report_parts.append(f"--- {step_name} [{state}] ---\n{result}\n")

        report = "\n".join(report_parts)
        self._last_report = report

        self.report_label.configure(text=report, fg=config.FG_PRIMARY)
        self.progress_label.configure(
            text=f"Completed: {run.workflow_name}",
            fg=config.FG_SUCCESS
        )
        self.loading.hide()
        self.app.set_status("idle", f"{run.workflow_name} complete")

        # Fill progress bar
        self.progress_bar.delete("all")
        self.progress_bar.update_idletasks()
        w = self.progress_bar.winfo_width()
        self.progress_bar.create_rectangle(0, 0, w, 8, fill=config.FG_SUCCESS, outline="")
