
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui import window_sizing
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import (
    make_toplevel, messagebox,
)
import sys
import os
from education_system.systems.university.infrastructure.database.db import sqlite3
import threading
import logging

from education_system.platform.delivery.gui.tk_threads import start_thread, ui
from datetime import datetime, timedelta
from education_system.systems.university.infrastructure.i18n import get_text

# Import health portal modules
try:
    from education_system.systems.university.domains.health.interfaces.gui.health.health_portal import HealthPortalGUI as _HealthPortalGUI
    HEALTH_PORTAL_GUI_AVAILABLE = True
    _HEALTH_PORTAL_GUI_IMPORT_ERROR = None
except ImportError as e:
    print(get_text("health.portal_management.gui_not_available", error=str(e), default="Gui Not Available {error}"))
    _HealthPortalGUI = None
    HEALTH_PORTAL_GUI_AVAILABLE = False
    _HEALTH_PORTAL_GUI_IMPORT_ERROR = str(e)

# Import shared database path if available
try:
    from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
    DB_PATH = str(UNIVERSITY_DEFAULT_DB_PATH)
except ImportError:
    DB_PATH = None

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.i18n import get_text, _

# Configure logging
logger = logging.getLogger(__name__)

class HealthPortalManagementGUI:
    """Health Portal management GUI wrapper"""

    def __init__(self, parent_root, auth_manager):
        self.root = parent_root
        self.auth = auth_manager

    def open_health_portal_gui(self):
        """Open the Health Portal GUI in a child window from the main app."""
        try:
            if not HEALTH_PORTAL_GUI_AVAILABLE:
                raise ImportError(get_text("health.portal_management.gui_unavailable", error=_HEALTH_PORTAL_GUI_IMPORT_ERROR, default="Gui Unavailable {error}"))

            # A child window of the main app at the GUI convention size
            # (1400x900, at least 1200x800, clamped to the screen). It is not
            # modal: the main window stays usable while the portal is open.
            win = make_toplevel(self.root)
            win.title(get_text("health.portal_management.window_title", default="Health Portal"))
            window_sizing.install()
            window_sizing.center(win, *_HealthPortalGUI.WINDOW_SIZE,
                                 minsize=_HealthPortalGUI.WINDOW_MINSIZE)
            win.configure(bg='#f0f0f0')

            # The portal opens its own connections through the health storage
            # adapter (infrastructure/health/storage), the same store the main
            # app and the health CLI use, so nothing is injected here.
            _HealthPortalGUI(win, auth_system=self.auth)

            logger.info(get_text("health.portal_management.opened_success",
                                 default="Health Portal opened"))

        except Exception as e:
            messagebox.showerror(get_text("health.portal_management.title", default="===== PORTAL MANAGEMENT ====="), get_text("health.portal_management.open_failed", error=str(e), default="Open Failed {error}"))

    def create_health_tab(self, parent):
        """Create system health monitoring tab"""
        health_container = ttk.Frame(parent, padding="20")
        health_container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(health_container, text=get_text("health.portal_management.system_health_monitoring", default="System Health Monitoring"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Health checks
        health_frame = ttk.LabelFrame(health_container, text=get_text("health.portal_management.health_checks", default="Health Checks"), padding="15")
        health_frame.pack(fill=tk.X, pady=(0, 20))

        # Add health monitoring functionality here
        checks = [
            ("Database Connection", self._check_database),
            ("Authentication System", self._check_auth),
            ("File System Access", self._check_filesystem),
            ("GUI Components", self._check_gui_components)
        ]

        for i, (check_name, check_func) in enumerate(checks):
            check_frame = ttk.Frame(health_frame)
            check_frame.pack(fill=tk.X, pady=5)

            ttk.Label(check_frame, text=check_name, width=25).pack(side=tk.LEFT)

            status_var = tk.StringVar(value=_t('gui.pastoral.health.health_portal_management.values.checking', default="Checking..."))
            status_label = ttk.Label(check_frame, textvariable=status_var)
            status_label.pack(side=tk.LEFT, padx=(10, 0))

            # Run the check in the background; the result is shown from the
            # Tk thread (Tk variables must not be set from another thread).
            def run_check(func=check_func, var=status_var, widget=status_label):
                try:
                    text = "✅ OK" if func() else "❌ FAIL"
                except Exception as e:
                    text = f"❌ ERROR: {str(e)[:50]}"
                ui(widget, var.set, text)

            start_thread(status_label, run_check)

    def _check_database(self):
        """Check the health store (the storage adapter the portal uses)."""
        try:
            if DB_PATH and not os.path.exists(DB_PATH):
                return False
            from education_system.systems.university.domains.health.infrastructure.health.storage import (
                get_connection,
            )
            conn = get_connection()
            try:
                conn.execute("SELECT 1 FROM health_records LIMIT 1")
            finally:
                conn.close()
            return True
        except Exception:
            return False

    def _check_auth(self):
        """Check authentication system"""
        return self.auth is not None and hasattr(self.auth, 'current_user')

    def _check_filesystem(self):
        """Check file system access"""
        try:
            import tempfile
            with tempfile.NamedTemporaryFile() as tmp:
                tmp.write(b"test")
            return True
        except Exception:
            return False

    def _check_gui_components(self):
        """Check GUI component availability"""
        return HEALTH_PORTAL_GUI_AVAILABLE