"""ClaudeClient — subprocess wrapper for claude -p."""
import json
import os
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from typing import Optional, Callable

from . import config


@dataclass
class ClaudeResponse:
    result: str
    cost_usd: float = 0.0
    duration_ms: int = 0
    session_id: str = ""
    error: Optional[str] = None

    @property
    def is_error(self):
        return self.error is not None


class ClaudeClient:
    def __init__(self, claude_path=None, max_budget_usd=None):
        self.claude_path = claude_path or config.get_setting("claude_path", config.DEFAULT_CLAUDE_PATH)
        self.max_budget_usd = max_budget_usd or config.get_setting("budget_usd", config.DEFAULT_BUDGET_USD)

    def call(self, prompt: str, system_append: str = "",
             timeout: int = 180) -> ClaudeResponse:
        """Blocking call to Claude CLI. Returns parsed response.

        Uses stdin piping (-p -) for the prompt and temp file for system prompt.
        This avoids Windows cmdline length/escaping issues entirely.
        """
        system_file = None

        try:
            cmd = [
                self.claude_path, "-p", "-",
                "--output-format", "json",
                "--allowedTools", "",
                "--max-budget-usd", str(self.max_budget_usd),
            ]

            # System prompt via temp file
            if system_append:
                system_file = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False, encoding="utf-8"
                )
                system_file.write(system_append)
                system_file.close()
                cmd += ["--append-system-prompt", system_file.name]

            # Pipe prompt via stdin, use shell=True for Windows .cmd wrapper
            result = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True,
                timeout=timeout, shell=True,
                cwd=config.BASE_DIR
            )

        except subprocess.TimeoutExpired:
            return ClaudeResponse(result="", error=f"Claude timed out after {timeout}s")
        except FileNotFoundError:
            return ClaudeResponse(result="", error=f"Claude CLI not found at '{self.claude_path}'")
        finally:
            if system_file:
                try:
                    os.unlink(system_file.name)
                except OSError:
                    pass

        if result.returncode != 0:
            stderr = result.stderr.strip()
            return ClaudeResponse(result="", error=f"Claude error (rc={result.returncode}): {stderr}")

        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            return ClaudeResponse(result="", error=f"Invalid JSON from Claude: {result.stdout[:200]}")

        return ClaudeResponse(
            result=data.get("result", ""),
            cost_usd=data.get("total_cost_usd", 0),
            duration_ms=data.get("duration_ms", 0),
            session_id=data.get("session_id", ""),
        )

    def call_async(self, prompt: str, system_append: str = "",
                   timeout: int = 180,
                   callback: Optional[Callable] = None) -> threading.Thread:
        """Non-blocking call. Runs in a thread, calls callback(ClaudeResponse) when done."""
        def _run():
            resp = self.call(prompt, system_append, timeout)
            if callback:
                callback(resp)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t
