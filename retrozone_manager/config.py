"""GUI config — colors, fonts, paths, defaults."""
import os
import json

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "retro_store.db")
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

# Defaults
DEFAULT_CLAUDE_PATH = "claude"
DEFAULT_BUDGET_USD = 1.0
DEFAULT_REFRESH_MS = 30000

# Colors (dark theme)
BG_DARK = "#1a1a2e"
BG_PANEL = "#16213e"
BG_CARD = "#0f3460"
BG_SIDEBAR = "#0a0a1a"
BG_INPUT = "#1a1a3e"
FG_PRIMARY = "#e0e0e0"
FG_SECONDARY = "#a0a0b0"
FG_ACCENT = "#e94560"
FG_SUCCESS = "#4ecca3"
FG_WARNING = "#ffd93d"
FG_DANGER = "#ff6b6b"
FG_INFO = "#6bcbff"
BORDER_COLOR = "#2a2a4a"

# Risk colors
RISK_COLORS = {
    "low": FG_SUCCESS,
    "medium": FG_WARNING,
    "high": FG_DANGER,
}

# Fonts
FONT_FAMILY = "Segoe UI"
FONT_SIZE = 10
FONT_SIZE_LARGE = 14
FONT_SIZE_SMALL = 9
FONT_SIZE_TITLE = 18

# Window
WINDOW_TITLE = "RetroZone Manager"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 750


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_setting(key, default=None):
    s = load_settings()
    return s.get(key, default)
