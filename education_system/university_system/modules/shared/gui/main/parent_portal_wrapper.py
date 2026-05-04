"""Parent Portal GUI wrapper — the landing page for parent users.

Launches the existing ParentPortalGUI in a dedicated Tk root window with
Return to Login and Shutdown buttons, matching the other role portals.
"""

import tkinter as tk
from tkinter import ttk
import logging

logger = logging.getLogger(__name__)


class ParentPortalWrapper:
    """Wrapper that presents the existing ParentPortalGUI as the primary window."""

    def __init__(self, auth_manager):
        self.auth = auth_manager
        self.root = tk.Tk()
        try:
            from education_system.university_system.modules.shared.gui.main._tk_callback_filter import (
                install_destroy_race_filter,
            )
            install_destroy_race_filter(self.root)
        except Exception:
            pass
        self.root.title("Parent Portal")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        self._build_header()
        self._launch_portal()

        self.root.protocol("WM_DELETE_WINDOW", self._shutdown)

    def _build_header(self):
        header = tk.Frame(self.root, bg='#2c3e50', height=50)
        header.pack(fill='x')
        header.pack_propagate(False)

        username = ''
        if self.auth and self.auth.current_user:
            username = self.auth.current_user.get('display_name') or self.auth.current_user.get('username', '')

        tk.Label(header, text=f"Parent Portal — {username}",
                 font=('Arial', 15, 'bold'), bg='#2c3e50', fg='white'
                 ).pack(side='left', padx=20, pady=10)

        tk.Button(header, text="Shutdown", bg='#c0392b', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._shutdown).pack(side='right', padx=10, pady=10)

        tk.Button(header, text="Return to Login", bg='#e67e22', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._return_to_login).pack(side='right', padx=10, pady=10)

    def _launch_portal(self):
        """Embed the existing ParentPortalGUI inside our root window."""
        try:
            from education_system.university_system.modules.domain.academics.gui.parent_portal.base import ParentPortalGUI
            portal = ParentPortalGUI(self.auth)
            # Re-parent the portal into our root
            portal.root = self.root
            portal.setup_layout()
            portal.load_user_data()
        except Exception as e:
            logger.error(f"Error loading parent portal: {e}")
            ttk.Label(self.root, text="Welcome, parent!",
                      font=('Arial', 14, 'bold')).pack(pady=20)
            ttk.Label(self.root,
                      text=f"The parent portal could not be loaded: {e}",
                      font=('Arial', 11), foreground='red').pack()

    def _return_to_login(self):
        if self.auth:
            try:
                self.auth.logout()
            except Exception:
                pass
        self._relaunch_after_logout = True
        self.root.destroy()

    def _shutdown(self):
        if self.auth:
            try:
                self.auth.logout()
            except Exception:
                pass
        self.root.destroy()
        raise SystemExit(0)

    def run(self):
        self._relaunch_after_logout = False
        self.root.mainloop()
        if getattr(self, '_relaunch_after_logout', False):
            try:
                from education_system.shared.gui.login_gui import UniversalLoginWindow
                login = UniversalLoginWindow()
                login.mainloop()
                if login.user_info and login.system_key:
                    from education_system.launcher.systems import run_university_gui
                    run_university_gui(
                        user_info=login.user_info,
                        role=login.system_role,
                        shared_auth=login.auth,
                    )
            except Exception as e:
                logger.error(f"Error returning to login: {e}")
