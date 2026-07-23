"""Alumni Portal GUI wrapper — the landing page for alumni users.

Launches the existing Alumni Management GUI in a dedicated Tk root window with
Return to Login and Shutdown buttons, matching the other role portals. Users
whose university role is 'alumni' (set when they graduate) land here instead of
the student portal.
"""

import tkinter as tk
from tkinter import ttk
import logging

logger = logging.getLogger(__name__)


class AlumniPortalWrapper:
    """Presents the existing Alumni Management GUI as the primary window."""

    def __init__(self, auth_manager):
        self.auth = auth_manager
        self.root = tk.Tk()
        try:
            from education_system.post_18.university_system.modules.shared.gui.main._tk_callback_filter import (
                install_destroy_race_filter,
            )
            install_destroy_race_filter(self.root)
        except Exception:
            pass
        self.root.title("Alumni Portal")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        self._build_header()
        self._build_announcements()
        self._launch_portal()

        self.root.protocol("WM_DELETE_WINDOW", self._shutdown)

    def _build_announcements(self):
        """Show university announcements (from the Communications GUI) at the
        top of the alumni portal. Alumni see 'all'-audience announcements."""
        try:
            from education_system.post_18.university_system.modules.shared.gui.main.dashboard.announcements_widget import (
                create_announcements_panel,
            )
            create_announcements_panel(self.root, self.auth, limit=3)
        except Exception as e:
            logger.warning(f"Announcements unavailable: {e}")

    def _build_header(self):
        header = tk.Frame(self.root, bg='#2c3e50', height=50)
        header.pack(fill='x')
        header.pack_propagate(False)

        username = ''
        if self.auth and self.auth.current_user:
            username = self.auth.current_user.get('display_name') or self.auth.current_user.get('username', '')

        tk.Label(header, text=f"Alumni Portal — {username}",
                 font=('Arial', 15, 'bold'), bg='#2c3e50', fg='white'
                 ).pack(side='left', padx=20, pady=10)

        # Logout (Return to Login) and Shutdown are the only two actions for an
        # alumnus — there is no "return to dashboard". Spread them evenly across
        # the remaining header width via an expanding container.
        actions = tk.Frame(header, bg='#2c3e50')
        actions.pack(side='right', fill='x', expand=True)

        tk.Button(actions, text="💬 Assistant", bg='#2980b9', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._open_chatbot).pack(side='left', expand=True, pady=10)

        tk.Button(actions, text="Return to Login", bg='#e67e22', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._return_to_login).pack(side='left', expand=True, pady=10)

        tk.Button(actions, text="Shutdown", bg='#c0392b', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._shutdown).pack(side='left', expand=True, pady=10)

    def _launch_portal(self):
        """Embed the existing Alumni Management GUI inside our root window."""
        try:
            from education_system.post_18.university_system.modules.domain.student_affairs.gui.alumni.main_gui import (
                AlumniGUIApp,
            )
            AlumniGUIApp(self.root, auth=self.auth, show_return_button=False)
        except Exception as e:
            logger.error(f"Error loading alumni portal: {e}")
            ttk.Label(self.root, text="Welcome to the Alumni community!",
                      font=('Arial', 14, 'bold')).pack(pady=20)
            ttk.Label(self.root,
                      text=f"The alumni portal could not be loaded: {e}",
                      font=('Arial', 11), foreground='red').pack()

    def _open_chatbot(self):
        """Open the University Chatbot assistant in its own window."""
        from tkinter import messagebox
        try:
            from education_system.post_18.university_system.infrastructure.ai.university_chatbot import (
                UniversityChatbot,
            )
            from education_system.post_18.university_system.infrastructure.ai.gui.chatbot_gui import (
                ChatbotGUI,
            )
        except Exception as e:
            logger.error(f"Chatbot unavailable: {e}")
            messagebox.showerror("Assistant", f"The assistant is not available: {e}")
            return

        try:
            chatbot = UniversityChatbot()
            if self.auth:
                try:
                    chatbot.set_auth_system(self.auth)
                except Exception:
                    pass

            chatbot_window = tk.Toplevel(self.root)
            chatbot_window.title("University Assistant")
            chatbot_window.geometry("1000x700")

            # ChatbotGUI wires its own window-close handler and (with a parent
            # window passed) renders into this Toplevel, leaving the portal open.
            ChatbotGUI(chatbot, chatbot_window, auth_system=self.auth)
        except Exception as e:
            logger.error(f"Error opening chatbot: {e}")
            messagebox.showerror("Assistant", f"Could not open the assistant: {e}")

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
