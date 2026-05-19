"""WorkflowEngine — state machine, threading, approval gates."""
import threading
import tkinter as tk
from typing import Optional, Callable
from . import config
from .claude_client import ClaudeClient
from .db_layer import StoreDB
from .prompts.system_context import build_system_prompt, build_system_prompt_with_tools


# Workflow step states
class StepState:
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    ERROR = "error"


class WorkflowRun:
    """Tracks a single workflow execution."""
    def __init__(self, workflow_name, steps):
        self.workflow_name = workflow_name
        self.steps = steps  # list of step names
        self.current_step = 0
        self.step_states = {i: StepState.PENDING for i in range(len(steps))}
        self.step_results = {}
        self.proposals = []  # actions pending approval
        self.report = ""  # final report text
        self.error = None

    @property
    def state(self):
        if self.error:
            return StepState.ERROR
        if all(s == StepState.COMPLETED for s in self.step_states.values()):
            return StepState.COMPLETED
        if any(s == StepState.WAITING_APPROVAL for s in self.step_states.values()):
            return StepState.WAITING_APPROVAL
        if any(s == StepState.RUNNING for s in self.step_states.values()):
            return StepState.RUNNING
        return StepState.PENDING


class WorkflowEngine:
    """Runs workflows in background threads, handles approval gates."""

    def __init__(self, app):
        self.app = app
        self.db = StoreDB()
        self.claude = ClaudeClient()
        self.current_run: Optional[WorkflowRun] = None
        self._on_update: Optional[Callable] = None
        self._on_approval_needed: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None

    def set_callbacks(self, on_update=None, on_approval_needed=None, on_complete=None):
        self._on_update = on_update
        self._on_approval_needed = on_approval_needed
        self._on_complete = on_complete

    def _do_analyze(self, run, step_idx, workflow, step):
        """Run Claude analysis — no approval needed."""
        prompt = step.get("prompt") or workflow.build_analyze_prompt()
        system = build_system_prompt(step.get("system_extra", ""))

        def on_response(resp):
            if resp.is_error:
                run.step_states[step_idx] = StepState.ERROR
                run.error = resp.error
            else:
                run.step_results[step_idx] = resp.result
                run.step_states[step_idx] = StepState.COMPLETED
                self.app.after(0, lambda: self.app.add_cost(resp.cost_usd))
            self._notify_update()

        # Run Claude call synchronously in this thread
        resp = self.claude.call(prompt, system_append=system)
        on_response(resp)

    def _do_propose(self, run, step_idx, workflow, step):
        """Claude proposes actions — needs approval."""
        analyze_result = run.step_results.get(step_idx - 1, "")
        prompt = step.get("prompt") or workflow.build_propose_prompt(analyze_result)
        system = build_system_prompt(step.get("system_extra", ""))

        resp = self.claude.call(prompt, system_append=system)
        self.app.after(0, lambda: self.app.add_cost(resp.cost_usd))

        if resp.is_error:
            run.step_states[step_idx] = StepState.ERROR
            run.error = resp.error
            self._notify_update()
            return

        proposals = workflow.parse_proposals(resp.result)
        run.proposals = proposals
        run.step_results[step_idx] = resp.result
        run.step_states[step_idx] = StepState.WAITING_APPROVAL
        self._notify_update()

        # Notify UI that approval is needed
        if self._on_approval_needed:
            self.app.after(0, self._on_approval_needed, run, proposals)

    def _do_execute(self, run, step_idx, workflow, step):
        """Execute approved actions in DB."""
        approved = getattr(run, '_approved_actions', [])
        proposals = run.proposals

        if not approved:
            run.step_states[step_idx] = StepState.COMPLETED
            run.step_results[step_idx] = "No actions approved"
            self._notify_update()
            return

        results = []
        for idx in approved:
            if idx < len(proposals):
                action = proposals[idx]
                try:
                    workflow.execute_action(action)
                    results.append(f"OK: {action['description']}")
                except Exception as e:
                    results.append(f"ERROR: {action['description']} — {e}")

        run.step_results[step_idx] = "\n".join(results)
        run.step_states[step_idx] = StepState.COMPLETED
        self._notify_update()

    def _do_research(self, run, step_idx, workflow, step):
        """Run Claude with external tools enabled — longer timeout, tool access."""
        prompt = step.get("prompt", "")
        if not prompt and hasattr(workflow, "build_research_prompt"):
            prompt = workflow.build_research_prompt()

        system = build_system_prompt_with_tools(step.get("system_extra", ""))

        # Research steps get longer timeout and tool access
        timeout = step.get("timeout", 300)
        allowed_tools = "mcp__retro-tools__*,mcp__web-reader__*"

        resp = self.claude.call(
            prompt, system_append=system,
            timeout=timeout, allowed_tools=allowed_tools
        )
        self.app.after(0, lambda: self.app.add_cost(resp.cost_usd))

        if resp.is_error:
            run.step_states[step_idx] = StepState.ERROR
            run.error = resp.error
        else:
            run.step_results[step_idx] = resp.result
            run.step_states[step_idx] = StepState.COMPLETED
        self._notify_update()

    def approve(self, approved_indices):
        """Called from UI when human approves actions."""
        if self.current_run:
            self.current_run._approved_actions = approved_indices
            # Continue execution
            for idx, state in self.current_run.step_states.items():
                if state == StepState.WAITING_APPROVAL:
                    self.current_run.step_states[idx] = StepState.APPROVED
                    break
            self._notify_update()

            # Resume execution in new thread
            run = self.current_run
            workflow = self._current_workflow

            def _continue():
                try:
                    # Run execute step
                    execute_step_idx = idx + 1
                    if execute_step_idx < len(run.steps):
                        step = workflow.get_steps()[execute_step_idx]
                        run.current_step = execute_step_idx
                        run.step_states[execute_step_idx] = StepState.RUNNING
                        self._notify_update()
                        self._do_execute(run, execute_step_idx, workflow, step)

                    if run.state == StepState.COMPLETED and self._on_complete:
                        self.app.after(0, self._on_complete, run)
                except Exception as e:
                    run.error = str(e)
                    self._notify_update()

            threading.Thread(target=_continue, daemon=True).start()

    def reject(self):
        """Called from UI when human rejects."""
        if self.current_run:
            for idx, state in self.current_run.step_states.items():
                if state == StepState.WAITING_APPROVAL:
                    self.current_run.step_states[idx] = StepState.REJECTED
                    break
            self.current_run.report = "Rejected by operator"
            self._notify_update()
            if self._on_complete:
                self.app.after(0, self._on_complete, self.current_run)

    def _notify_update(self):
        if self._on_update:
            self.app.after(0, self._on_update, self.current_run)

    _current_workflow = None

    def run_workflow(self, workflow):
        if self.current_run and self.current_run.state in (StepState.RUNNING, StepState.WAITING_APPROVAL):
            return

        self._current_workflow = workflow
        steps = workflow.get_steps()
        run = WorkflowRun(workflow.name, [s["name"] for s in steps])
        self.current_run = run

        def _execute():
            try:
                for i, step in enumerate(steps):
                    run.current_step = i
                    run.step_states[i] = StepState.RUNNING
                    self._notify_update()

                    if step["type"] == "analyze":
                        self._do_analyze(run, i, workflow, step)
                    elif step["type"] == "propose":
                        self._do_propose(run, i, workflow, step)
                    elif step["type"] == "execute":
                        self._do_execute(run, i, workflow, step)
                    elif step["type"] == "research":
                        self._do_research(run, i, workflow, step)

                    if run.step_states[i] in (StepState.ERROR, StepState.REJECTED):
                        break
                    if run.step_states[i] == StepState.WAITING_APPROVAL:
                        break  # will resume after approve()

                if run.state == StepState.COMPLETED and self._on_complete:
                    self.app.after(0, self._on_complete, run)

            except Exception as e:
                run.error = str(e)
                run.step_states[run.current_step] = StepState.ERROR
                self._notify_update()

        threading.Thread(target=_execute, daemon=True).start()
