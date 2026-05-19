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
             timeout: int = 180,
             allowed_tools: str = "") -> ClaudeResponse:
        """Blocking call to Claude CLI. Returns parsed response.

        Uses stdin piping (-p -) for the prompt and temp file for system prompt.
        This avoids Windows cmdline length/escaping issues entirely.

        Args:
            allowed_tools: Comma-separated tool patterns for --allowedTools.
                Empty string (default) = no tools. Use "mcp__retro-tools__*,mcp__web-reader__*"
                to enable external tools.
        """
        system_file = None

        try:
            cmd = [
                self.claude_path, "-p", "-",
                "--output-format", "json",
                "--allowedTools", allowed_tools,
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
            # Use Popen for proper cleanup on timeout (subprocess.run doesn't
            # kill child processes on Windows when shell=True)
            proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, shell=True,
                cwd=config.BASE_DIR,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
            try:
                stdout, stderr = proc.communicate(input=prompt, timeout=timeout)
                result = subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
            except subprocess.TimeoutExpired:
                # On Windows, terminate the process group to kill all children
                proc.kill()
                proc.wait(timeout=5)
                return ClaudeResponse(result="", error=f"Claude timed out after {timeout}s")

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
                   callback: Optional[Callable] = None,
                   allowed_tools: str = "") -> threading.Thread:
        """Non-blocking call. Runs in a thread, calls callback(ClaudeResponse) when done."""
        def _run():
            resp = self.call(prompt, system_append, timeout, allowed_tools=allowed_tools)
            if callback:
                callback(resp)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t
