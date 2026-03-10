import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
from education_system.university_system.infrastructure.database.db import sqlite3
import threading
import logging
from datetime import datetime, timedelta

# Import health portal modules
try:
    from education_system.university_system.modules.domain.health.gui.health_portal_gui import HealthPortalGUI as _HealthPortalGUI
    HEALTH_PORTAL_GUI_AVAILABLE = True
    _HEALTH_PORTAL_GUI_IMPORT_ERROR = None
except ImportError as e:
    print(get_text("health.portal_management.gui_not_available", error=str(e)))
    _HealthPortalGUI = None
    HEALTH_PORTAL_GUI_AVAILABLE = False
    _HEALTH_PORTAL_GUI_IMPORT_ERROR = str(e)

# Import shared database path if available
try:
    from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
    DB_PATH = str(DEFAULT_DB_PATH)
except ImportError:
    DB_PATH = None

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.shared.utils.i18n import get_text, _

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
                raise ImportError(get_text("health.portal_management.gui_unavailable", error=_HEALTH_PORTAL_GUI_IMPORT_ERROR))

            # Create a child window
            win = tk.Toplevel(self.root)
            win.title(get_text("health.portal_management.window_title"))
            win.geometry("1400x900")

            # Configure window background
            win.configure(bg='#f0f0f0')

            # Make it feel modal without blocking the main loop
            try:
                win.transient(self.root)
                win.grab_set()
            except Exception as e:
                logger.debug(f"Could not set window as transient or grab focus: {e}")

            # Instantiate the portal GUI with auth system
            app = _HealthPortalGUI(win, auth_system=self.auth)

            # Make the portal use the SAME DB as the main app (if DB_PATH exists)
            try:
                if DB_PATH:
                    # If the portal exposes a get_connection hook, align it with main DB
                    if hasattr(app, 'get_connection'):
                        app.get_connection = (lambda db_path=DB_PATH, _s=sqlite3: _s.connect(db_path))
            except Exception as e:
                # Not fatal—portal will fall back to its default connection strategy
                logger.debug(f"Could not inject database connection: {e}")

            print(get_text("health.portal_management.opened_success"))

        except Exception as e:
            messagebox.showerror(get_text("health.portal_management.title"), get_text("health.portal_management.open_failed", error=str(e)))

    def create_health_tab(self, parent):
        """Create system health monitoring tab"""
        health_container = ttk.Frame(parent, padding="20")
        health_container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(health_container, text=get_text("health.portal_management.system_health_monitoring"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Health checks
        health_frame = ttk.LabelFrame(health_container, text=get_text("health.portal_management.health_checks"), padding="15")
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

            status_var = tk.StringVar(value="Checking...")
            status_label = ttk.Label(check_frame, textvariable=status_var)
            status_label.pack(side=tk.LEFT, padx=(10, 0))

            # Run check in background
            def run_check(func=check_func, var=status_var):
                try:
                    result = func()
                    var.set("✅ OK" if result else "❌ FAIL")
                except Exception as e:
                    var.set(f"❌ ERROR: {str(e)[:50]}")

            threading.Thread(target=run_check, daemon=True).start()

    def _check_database(self):
        """Check database connectivity"""
        try:
            if DB_PATH and os.path.exists(DB_PATH):
                conn = sqlite3.connect(DB_PATH)
                conn.execute("SELECT 1")
                conn.close()
                return True
            return False
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