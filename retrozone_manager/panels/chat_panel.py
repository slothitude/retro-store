"""Chat panel — direct conversation with Claude about the store."""
import tkinter as tk
from .. import config
from ..claude_client import ClaudeClient
from ..prompts.system_context import build_system_prompt, build_system_prompt_with_tools
from ..db_layer import StoreDB
from ..widgets.scrollable import ScrollableFrame
import threading
import time


class ChatPanel(tk.Frame):
    def __init__(self, parent, app=None, **kw):
        super().__init__(parent, bg=config.BG_PANEL, **kw)
        self.app = app
        self.client = ClaudeClient()
        self.db = StoreDB()
        self.messages = []  # list of (role, text, timestamp)
        self._claude_busy = False
        self._tools_enabled = False  # Toggle: False = Local, True = Connected
        self._build()

    def _build(self):
        # Title bar
        header = tk.Frame(self, bg=config.BG_PANEL)
        header.pack(fill="x", padx=20, pady=(15, 5))
        tk.Label(header, text="Chat with RetroZone AI",
                 font=(config.FONT_FAMILY, config.FONT_SIZE_TITLE, "bold"),
                 bg=config.BG_PANEL, fg=config.FG_PRIMARY).pack(side="left")
        tk.Label(header, text="Ask anything about your store, inventory, orders, or strategy",
                 font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                 bg=config.BG_PANEL, fg=config.FG_SECONDARY).pack(side="left", padx=(15, 0))

        # Tools toggle button
        self.tools_btn = tk.Button(
            header, text="\u26A3 Local", font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
            bg=config.BG_CARD, fg=config.FG_SECONDARY, bd=1, relief="solid",
            padx=8, pady=2, cursor="hand2", command=self._toggle_tools
        )
        self.tools_btn.pack(side="right", padx=(10, 0))

        # Chat history area (scrollable)
        self.scroll_area = ScrollableFrame(self)
        self.scroll_area.pack(fill="both", expand=True, padx=10, pady=(0, 0))

        self.chat_inner = self.scroll_area.scroll_frame

        # Welcome message
        self._add_message("assistant",
            "Hey! I'm Retro — your RetroZone AI manager. I know your full store state — inventory, "
            "orders, batches, tickets. Ask me anything:\n\n"
            "  - \"How's my inventory looking?\"\n"
            "  - \"Which products should I reorder?\"\n"
            "  - \"What's my best margin product?\"\n"
            "  - \"Any batches I should worry about?\"\n"
            "  - \"Give me a quick sales summary\"\n\n"
            "Toggle [Connected] mode (top-right) to search Alibaba, check eBay prices, and manage emails!")

        # Input area
        input_frame = tk.Frame(self, bg=config.BG_SIDEBAR, padx=10, pady=10)
        input_frame.pack(fill="x", side="bottom")

        self.input_entry = tk.Text(input_frame, height=3, wrap="word",
                                    font=(config.FONT_FAMILY, config.FONT_SIZE),
                                    bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                                    insertbackground=config.FG_PRIMARY,
                                    bd=0, relief="flat", padx=10, pady=8)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.input_entry.bind("<Return>", self._on_enter)
        self.input_entry.bind("<Shift-Return>", lambda e: None)  # allow shift+enter for newline

        self.send_btn = tk.Button(input_frame, text="Send", command=self._send_message,
                                   bg=config.FG_ACCENT, fg="#ffffff",
                                   font=(config.FONT_FAMILY, config.FONT_SIZE, "bold"),
                                   bd=0, padx=20, pady=8, cursor="hand2")
        self.send_btn.pack(side="right")

        self.typing_label = tk.Label(input_frame, text="", font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL),
                                      bg=config.BG_SIDEBAR, fg=config.FG_WARNING)
        self.typing_label.pack(side="right", padx=10)

    def _on_enter(self, event):
        # Send on Enter (without Shift), newlines with Shift+Enter
        if event.state & 0x1:  # Shift held
            return None  # allow default (newline)
        self._send_message()
        return "break"  # prevent default

    def _send_message(self):
        text = self.input_entry.get("1.0", "end").strip()
        if not text or self._claude_busy:
            return

        self._add_message("user", text)
        self.input_entry.delete("1.0", "end")

        self._claude_busy = True
        self.typing_label.configure(text="Retro is thinking...")
        if self.app:
            self.app.set_status("running", "Chat: thinking")

        # Build conversation context
        def _call_claude():
            try:
                # Build prompt with conversation history
                history = ""
                for role, msg, ts in self.messages[:-1]:  # exclude the just-added user msg
                    label = "You" if role == "user" else "Assistant"
                    history += f"{label}: {msg}\n\n"

                prompt = (
                    f"Conversation so far:\n{history}\n"
                    f"You: {text}\n\n"
                    f"Respond directly. Be concise and actionable. "
                    f"Reference specific data from the store state when relevant."
                )

                if self._tools_enabled:
                    system = build_system_prompt_with_tools()
                    allowed_tools = "mcp__retro-tools__*,mcp__web-reader__*"
                    timeout = 300
                else:
                    system = build_system_prompt()
                    allowed_tools = ""
                    timeout = 180

                print(f"[Chat] Calling Retro... (tools={'ON' if self._tools_enabled else 'OFF'}, {len(prompt)} chars prompt)")
                resp = self.client.call(prompt, system_append=system, timeout=timeout,
                                        allowed_tools=allowed_tools)
                print(f"[Chat] Response: error={resp.is_error}, cost=${resp.cost_usd:.4f}")

                # Schedule UI update on main thread
                if resp.is_error:
                    err = resp.error
                    self.after(0, lambda e=err: self._on_claude_error(e))
                else:
                    result = resp.result
                    cost = resp.cost_usd
                    self.after(0, lambda r=result, c=cost: self._on_claude_response(r, c))
            except Exception as e:
                print(f"[Chat] Thread error: {e}")
                self.after(0, lambda: self._on_claude_error(str(e)))

        threading.Thread(target=_call_claude, daemon=True).start()

    def _on_claude_response(self, result, cost):
        self._claude_busy = False
        self.typing_label.configure(text="")
        self._add_message("assistant", result)
        if self.app:
            self.app.add_cost(cost)
            self.app.set_status("idle", f"Chat: ${cost:.4f}")

    def _on_claude_error(self, error):
        self._claude_busy = False
        self.typing_label.configure(text="")
        self._add_message("system", f"Error: {error}")
        if self.app:
            self.app.set_status("error", f"Chat error: {error}")

    def _add_message(self, role, text):
        timestamp = time.strftime("%H:%M")
        self.messages.append((role, text, timestamp))

        # Message bubble
        bubble_frame = tk.Frame(self.chat_inner, bg=config.BG_PANEL)
        bubble_frame.pack(fill="x", padx=15, pady=3)

        if role == "user":
            # Right-aligned user message
            bubble = tk.Frame(bubble_frame, bg=config.FG_ACCENT, padx=12, pady=8)
            bubble.pack(anchor="e")
            tk.Label(bubble, text=text, font=(config.FONT_FAMILY, config.FONT_SIZE),
                     bg=config.FG_ACCENT, fg="#ffffff", wraplength=600, justify="left").pack(anchor="e")
            tk.Label(bubble_frame, text=timestamp, font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL - 1),
                     bg=config.BG_PANEL, fg=config.FG_SECONDARY).pack(anchor="e", padx=5)

        elif role == "assistant":
            # Left-aligned assistant message
            bubble = tk.Frame(bubble_frame, bg=config.BG_CARD, padx=12, pady=8)
            bubble.pack(anchor="w")
            tk.Label(bubble, text=text, font=(config.FONT_FAMILY, config.FONT_SIZE),
                     bg=config.BG_CARD, fg=config.FG_PRIMARY, wraplength=600, justify="left").pack(anchor="w")
            tk.Label(bubble_frame, text=f"Retro  {timestamp}", font=(config.FONT_FAMILY, config.FONT_SIZE_SMALL - 1),
                     bg=config.BG_PANEL, fg=config.FG_SECONDARY).pack(anchor="w", padx=5)

        else:  # system
            bubble = tk.Frame(bubble_frame, bg=config.BG_INPUT, padx=12, pady=8)
            bubble.pack(anchor="w")
            tk.Label(bubble, text=text, font=(config.FONT_FAMILY, config.FONT_SIZE),
                     bg=config.BG_INPUT, fg=config.FG_WARNING, wraplength=600).pack(anchor="w")

        # Auto-scroll to bottom
        self.scroll_area.canvas.update_idletasks()
        self.scroll_area.canvas.yview_moveto(1.0)

    def _toggle_tools(self):
        """Toggle between Local (no tools) and Connected (MCP tools) mode."""
        self._tools_enabled = not self._tools_enabled
        if self._tools_enabled:
            self.tools_btn.configure(text="\u26A3 Connected", bg=config.FG_SUCCESS,
                                      fg="#ffffff")
            self._add_message("system",
                "Connected mode ON — I can now search Alibaba, check eBay prices, "
                "manage emails, and track suppliers.")
        else:
            self.tools_btn.configure(text="\u26A3 Local", bg=config.BG_CARD,
                                      fg=config.FG_SECONDARY)
            self._add_message("system",
                "Local mode — external tools disabled. Only store data available.")
