"""Settings panel — Claude path, DB path, budget, refresh interval, email config."""
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
        row = 0
        for key, label, default in fields:
            tk.Label(form, text=label, font=(config.FONT_FAMILY, config.FONT_SIZE),
                     bg=config.BG_PANEL, fg=config.FG_SECONDARY).grid(
                row=row, column=0, sticky="w", pady=8)

            entry = tk.Entry(form, font=(config.FONT_FAMILY, config.FONT_SIZE),
                             bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                             insertbackground=config.FG_PRIMARY, bd=1, relief="flat",
                             width=40)
            entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=8)
            entry.insert(0, default)
            self.entries[key] = entry
            row += 1

        # Email config section
        sep = tk.Frame(form, bg=config.BORDER_COLOR, height=1)
        sep.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(15, 5))
        row += 1

        tk.Label(form, text="Email Configuration (IMAP/SMTP)",
                 font=(config.FONT_FAMILY, config.FONT_SIZE, "bold"),
                 bg=config.BG_PANEL, fg=config.FG_INFO).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(5, 10))
        row += 1

        email_fields = [
            ("imap_host", "IMAP Host:", "imap.gmail.com"),
            ("imap_port", "IMAP Port:", "993"),
            ("imap_user", "IMAP Username:", ""),
            ("imap_password", "IMAP Password:", ""),
            ("smtp_host", "SMTP Host:", "smtp.gmail.com"),
            ("smtp_port", "SMTP Port:", "587"),
            ("smtp_user", "SMTP Username:", ""),
            ("smtp_password", "SMTP Password:", ""),
        ]

        self.email_entries = {}
        for key, label, default in email_fields:
            tk.Label(form, text=label, font=(config.FONT_FAMILY, config.FONT_SIZE),
                     bg=config.BG_PANEL, fg=config.FG_SECONDARY).grid(
                row=row, column=0, sticky="w", pady=4)

            show = "*" if "password" in key else ""
            entry = tk.Entry(form, font=(config.FONT_FAMILY, config.FONT_SIZE),
                             bg=config.BG_INPUT, fg=config.FG_PRIMARY,
                             insertbackground=config.FG_PRIMARY, bd=1, relief="flat",
                             width=40, show=show if show else "")
            entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=4)
            if default:
                entry.insert(0, default)
            self.email_entries[key] = entry
            row += 1

        total_rows = row

        # Buttons
        btn_frame = tk.Frame(form, bg=config.BG_PANEL)
        btn_frame.grid(row=total_rows, column=0, columnspan=2, pady=20)

        tk.Button(btn_frame, text="Save", command=self._save,
                  bg=config.BG_CARD, fg=config.FG_PRIMARY,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=20, pady=8, cursor="hand2").pack(side="left", padx=5)

        tk.Button(btn_frame, text="Test Claude", command=self._test_claude,
                  bg=config.BG_CARD, fg=config.FG_INFO,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=20, pady=8, cursor="hand2").pack(side="left", padx=5)

        tk.Button(btn_frame, text="Test Email", command=self._test_email,
                  bg=config.BG_CARD, fg=config.FG_INFO,
                  font=(config.FONT_FAMILY, config.FONT_SIZE),
                  bd=0, padx=20, pady=8, cursor="hand2").pack(side="left", padx=5)

        self.status_label = tk.Label(form, text="", font=(config.FONT_FAMILY, config.FONT_SIZE),
                                      bg=config.BG_PANEL, fg=config.FG_SUCCESS)
        self.status_label.grid(row=total_rows + 1, column=0, columnspan=2, pady=5)

    def _load(self):
        settings = config.load_settings()
        for key, entry in self.entries.items():
            if key in settings:
                entry.delete(0, "end")
                entry.insert(0, str(settings[key]))
        for key, entry in self.email_entries.items():
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
        for key, entry in self.email_entries.items():
            val = entry.get().strip()
            if val:
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

    def _test_email(self):
        self.status_label.configure(text="Testing IMAP connection...", fg=config.FG_WARNING)
        self.update()

        try:
            import imaplib
            host = self.email_entries["imap_host"].get().strip()
            port = int(self.email_entries["imap_port"].get().strip() or "993")
            user = self.email_entries["imap_user"].get().strip()
            password = self.email_entries["imap_password"].get().strip()

            if not host or not user:
                self.status_label.configure(text="Enter IMAP host and username", fg=config.FG_WARNING)
                return

            mail = imaplib.IMAP4_SSL(host, port)
            mail.login(user, password)
            mail.select("INBOX", readonly=True)
            _, msg_ids = mail.search(None, "ALL")
            count = len(msg_ids[0].split()) if msg_ids[0] else 0
            mail.logout()

            self.status_label.configure(
                text=f"IMAP OK — {count} messages in INBOX",
                fg=config.FG_SUCCESS
            )
        except Exception as e:
            self.status_label.configure(text=f"IMAP Error: {e}", fg=config.FG_DANGER)
