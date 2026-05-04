"""OperationsConsole — single window unifying Activity Log, Audit
Viewer, Activity Logger, Log Analyzer and System Monitoring.

Lazy tab construction: each panel is built the first time its tab is
selected, not at window creation, so opening the console is fast and
embedded GUIs don't all spin up their background threads up front.
"""

import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)


# Tab keys used by both the console and the launcher's initial_tab arg.
TAB_ACTIVITY_LOG = "activity_log"
TAB_AUDIT_VIEWER = "audit_viewer"
TAB_ACTIVITY_LOGGER = "activity_logger"
TAB_LOG_ANALYZER = "log_analyzer"
TAB_SYSTEM_MONITORING = "system_monitoring"

_TAB_TITLES = {
    TAB_ACTIVITY_LOG: "Activity Log",
    TAB_AUDIT_VIEWER: "Audit Viewer",
    TAB_ACTIVITY_LOGGER: "Activity Logger",
    TAB_LOG_ANALYZER: "Log Analyzer",
    TAB_SYSTEM_MONITORING: "System Monitoring",
}

_TAB_ORDER = [
    TAB_ACTIVITY_LOG,
    TAB_AUDIT_VIEWER,
    TAB_ACTIVITY_LOGGER,
    TAB_LOG_ANALYZER,
    TAB_SYSTEM_MONITORING,
]


class OperationsConsole(tk.Toplevel):
    """Unified Toplevel + Notebook hosting all five panels."""

    def __init__(self, parent, auth=None, admin_user_id=None,
                 initial_tab=TAB_ACTIVITY_LOG):
        super().__init__(parent)
        self.title("Operations Console")
        self.geometry("1400x900")
        self.minsize(1100, 720)
        self.auth = auth
        self.admin_user_id = admin_user_id
        self._parent = parent

        # Per-tab state: each key maps to {'frame', 'built': bool, 'stop': fn}
        self._tabs = {}

        self._build_header()
        self._build_notebook()
        self._select_tab(initial_tab)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    def _build_header(self):
        header = tk.Frame(self, bg="#2C3E50", height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Operations Console",
                 font=("Arial", 14, "bold"),
                 bg="#2C3E50", fg="white").pack(side=tk.LEFT, padx=15, pady=10)
        ttk.Button(header, text="Close",
                   command=self._on_close).pack(side=tk.RIGHT, padx=10, pady=10)

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for key in _TAB_ORDER:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=_TAB_TITLES[key])
            self._tabs[key] = {'frame': frame, 'built': False, 'stop': None}

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _select_tab(self, key):
        if key not in self._tabs:
            key = TAB_ACTIVITY_LOG
        idx = _TAB_ORDER.index(key)
        self.notebook.select(idx)
        # Ensure the panel is built — tab-changed event covers re-clicks
        # but the very first select may not fire it on all Tk builds.
        self._ensure_built(key)

    def _on_tab_changed(self, _e=None):
        try:
            current = self.notebook.tab(self.notebook.select(), "text")
        except tk.TclError:
            return
        for key, title in _TAB_TITLES.items():
            if title == current:
                self._ensure_built(key)
                break

    def _ensure_built(self, key):
        info = self._tabs.get(key)
        if not info or info['built']:
            return
        info['built'] = True
        try:
            info['stop'] = self._build_panel(key, info['frame'])
        except Exception as e:
            logger.exception(f"Failed to build {key} panel")
            ttk.Label(info['frame'],
                      text=f"Failed to load {_TAB_TITLES[key]}: {e}",
                      foreground="#c62828").pack(padx=20, pady=20)

    def _build_panel(self, key, frame):
        if key == TAB_ACTIVITY_LOG:
            from education_system.university_system.modules.shared.gui.operations_console.activity_log import (
                build_activity_log_panel,
            )
            return build_activity_log_panel(frame, auth=self.auth).get('stop')
        if key == TAB_AUDIT_VIEWER:
            from education_system.university_system.modules.shared.gui.operations_console.audit_viewer import (
                build_audit_viewer_panel,
            )
            return build_audit_viewer_panel(
                frame, root_window=self,
                admin_user_id=self.admin_user_id).get('stop')
        if key == TAB_ACTIVITY_LOGGER:
            from education_system.university_system.modules.shared.gui.operations_console.activity_logger import (
                build_activity_logger_panel,
            )
            return build_activity_logger_panel(frame, auth=self.auth).get('stop')
        if key == TAB_LOG_ANALYZER:
            from education_system.university_system.modules.shared.gui.operations_console.log_analyzer import (
                build_log_analyzer_panel,
            )
            return build_log_analyzer_panel(frame).get('stop')
        if key == TAB_SYSTEM_MONITORING:
            from education_system.university_system.modules.shared.gui.operations_console.system_monitoring import (
                build_system_monitoring_panel,
            )
            return build_system_monitoring_panel(frame).get('stop')
        return None

    def _on_close(self):
        # Give each built panel a chance to cancel after-loops / threads.
        for info in self._tabs.values():
            stop = info.get('stop')
            if callable(stop):
                try:
                    stop()
                except Exception:
                    pass
        self.destroy()


def open_operations_console(parent, auth=None, admin_user_id=None,
                            initial_tab=TAB_ACTIVITY_LOG):
    """Public launcher used by config_gui.py and the Operations tab."""
    return OperationsConsole(parent, auth=auth,
                             admin_user_id=admin_user_id,
                             initial_tab=initial_tab)
