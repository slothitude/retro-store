"""RetroZoneApp — main window, sidebar, panel container, status bar."""
import tkinter as tk
from . import config
from .widgets.nav_sidebar import NavSidebar
from .widgets.status_bar import StatusBar
from .widgets.scrollable import ScrollableFrame


class RetroZoneApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(config.WINDOW_TITLE)
        self.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.configure(bg=config.BG_DARK)
        self.minsize(900, 550)

        # Panel registry — lazy loaded
        self._panels = {}
        self._current_panel = None

        # Layout
        self.sidebar = NavSidebar(self, on_navigate=self._switch_panel)
        self.sidebar.pack(side="left", fill="y")

        self.content = tk.Frame(self, bg=config.BG_PANEL)
        self.content.pack(side="left", fill="both", expand=True)

        self.status_bar = StatusBar(self)
        self.status_bar.pack(side="bottom", fill="x")

        # Show dashboard by default
        self._switch_panel("dashboard")

    def _get_panel(self, key):
        if key not in self._panels:
            panel_classes = {
                "dashboard": "panels.dashboard_panel",
                "orders": "panels.orders_panel",
                "batches": "panels.batches_panel",
                "suppliers": "panels.suppliers_panel",
                "tickets": "panels.tickets_panel",
                "workflows": "panels.workflows_panel",
                "chat": "panels.chat_panel",
                "settings": "panels.settings_panel",
            }
            if key not in panel_classes:
                return None

            # Lazy import
            module_path = f"{__package__}.{panel_classes[key]}"
            import importlib
            module = importlib.import_module(module_path)

            # Convention: class name is key + "Panel", title-cased
            class_name = key.replace("_", " ").title().replace(" ", "") + "Panel"
            panel_cls = getattr(module, class_name)

            # Chat panel handles its own scrolling, others get wrapped
            if key == "chat":
                self._panels[key] = panel_cls(self.content, app=self)
            else:
                # Wrap in scrollable container
                scroll = ScrollableFrame(self.content)
                panel = panel_cls(scroll.scroll_frame, app=self)
                panel.pack(fill="both", expand=True)
                self._panels[key] = scroll

        return self._panels[key]

    def _switch_panel(self, key):
        if self._current_panel:
            self._current_panel.pack_forget()

        panel = self._get_panel(key)
        if panel:
            panel.pack(fill="both", expand=True)
            self._current_panel = panel
            # Find inner panel for refresh
            inner = self._find_inner_panel(panel)
            if inner and hasattr(inner, "refresh"):
                inner.refresh()

    def _find_inner_panel(self, widget):
        """Find the actual panel widget (might be wrapped in ScrollableFrame)."""
        if isinstance(widget, ScrollableFrame):
            frame = widget.scroll_frame
            children = frame.winfo_children()
            return children[0] if children else None
        return widget

    def set_status(self, state, msg=""):
        self.status_bar.set_state(state, msg)

    def add_cost(self, usd):
        self.status_bar.add_cost(usd)
