"""Settings panel — Claude path, DB path, budget, refresh interval."""
import tkinter as tk
from .. import config


class SettingsPanel(tk.Frame):
    def __init__(self, parent, app=None, **kw):
        super().__init__(parent, bg=config.BG_PANEL, **kw)
        self.app = app
        self._build()
        self._load()

    def _build(self):
        tk.Label(self, text="Settings", font=(config.FONT_FAMILY, config.FONT_SIZE_TITLE, "bold"),
                 bg=config.BG_PANEL, fg=config.FG_PRIMARY).pack(anchor="w", padx=20, pady=(15, 20))

        form = tk.Frame(self, bg=config.BG_PANEL)
        form.pack(fill="both", expand=True, padx=20)

        fields = [
            ("claude_path", "Claude CLI Path:", config.DEFAULT_CLAUDE_PATH),
            ("db_path", "Database Path:", config.DB_PATH),
            ("budget_usd", "Max Budget per Call ($):", str(config.DEFAULT_BUDGET_USD)),
            ("refresh_ms", "Refresh Interval (ms):", str(config.DEFAULT_REFRESH_MS)),
        ]

        self.entries = {}
        for i, (key, label, default) in enumerate(fields):
            tk.Label(form, text=label, font=(config.FONT_FAMILY, config.FONT_SIZE),
                     bg=config.BG_PANEL, fg=config.FG_SECONDARY).grid(
                row=i, column=0, sticky="w", pady=8)

            entry = tk.Entry(form, font=(config.FONT_FAMILY, config.FONT_SIZE),
                             bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                             insertbackground=config.FG_PRIMARY, bd=1, relief="flat",
                             width=40)
            entry.grid(row=i, column=1, sticky="w", padx=(10, 0), pady=8)
            entry.insert(0, default)
            self.entries[key] = entry

        # Buttons
        btn_frame = tk.Frame(form, bg=config.BG_PANEL)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=20)

        tk.Button(btn_frame, text="Save", command=self._save,
                  bg=config.BG_CARD, fg=config.FG_PRIMARY,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=20, pady=8, cursor="hand2").pack(side="left", padx=5)

        tk.Button(btn_frame, text="Test Claude Connection", command=self._test_claude,
                  bg=config.BG_CARD, fg=config.FG_INFO,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=20, pady=8, cursor="hand2").pack(side="left", padx=5)

        self.status_label = tk.Label(form, text="", font=(config.FONT_FAMILY, config.FONT_SIZE),
                                      bg=config.BG_PANEL, fg=config.FG_SUCCESS)
        self.status_label.grid(row=len(fields) + 1, column=0, columnspan=2, pady=5)

    def _load(self):
        settings = config.load_settings()
        for key, entry in self.entries.items():
            if key in settings:
                entry.delete(0, "end")
                entry.insert(0, str(settings[key]))

    def _save(self):
        data = {}
        for key, entry in self.entries.items():
            val = entry.get().strip()
            if key in ("budget_usd", "refresh_ms"):
                try:
                    data[key] = float(val) if "budget" in key else int(val)
                except ValueError:
                    continue
            else:
                data[key] = val
        config.save_settings(data)
        self.status_label.configure(text="Settings saved", fg=config.FG_SUCCESS)

    def _test_claude(self):
        self.status_label.configure(text="Testing...", fg=config.FG_WARNING)
        self.update()

        from ..claude_client import ClaudeClient
        client = ClaudeClient(claude_path=self.entries["claude_path"].get().strip())
        resp = client.call("Say 'Connection successful' and nothing else.", timeout=30)

        if resp.is_error:
            self.status_label.configure(text=f"Error: {resp.error}", fg=config.FG_DANGER)
        else:
            self.status_label.configure(
                text=f"OK — {resp.result[:50]} (${resp.cost_usd:.4f}, {resp.duration_ms/1000:.1f}s)",
                fg=config.FG_SUCCESS
            )
