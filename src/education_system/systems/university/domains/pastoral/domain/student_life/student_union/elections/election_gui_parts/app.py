"""Extracted class implementation."""
import logging

logger = logging.getLogger(__name__)

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class App:
    """Auth-aware launcher: dispatches to the admin or voter dashboard
    based on the logged-in user's role. No login window — this assumes
    the parent process has already authenticated.
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Student Union Election System")
        self.root.geometry("1200x780")
        self.root.minsize(900, 600)
        self.root.configure(bg=BG)

        self.db = Database()
        setup_styles()

        self.user = self._resolve_user()
        if not self.user:
            self._show_no_auth()
        else:
            self._dispatch()

    def _resolve_user(self):
        """Pull the logged-in user from the global auth, or fall back to
        env vars (already consumed by _bootstrap_auth_from_env). Returns
        a dict with at least 'username', 'role', and ideally 'student_id'.
        """
        try:
            from education_system.systems.university.infrastructure.auth import (  # noqa: E501
                get_global_auth,
            )
            ga = get_global_auth()
            cu = getattr(ga, 'current_user', None) if ga else None
            if cu:
                return {
                    'id': cu.get('id') or cu.get('user_id'),
                    'user_id': cu.get('user_id') or cu.get('id'),
                    'username': cu.get('username', ''),
                    'role': cu.get('role', ''),
                    'email': cu.get('email', ''),
                    'student_id': cu.get('student_id')
                                  or cu.get('username', ''),
                    'name': cu.get('name')
                            or cu.get('username', ''),
                }
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        return None

    def _show_no_auth(self):
        for w in self.root.winfo_children():
            w.destroy()
        outer = ttk.Frame(self.root, style="TFrame")
        outer.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(outer, text="🔒 Authentication required",
                  style="Title.TLabel").pack(pady=(0, 6))
        ttk.Label(outer,
                  text="Launch this module from the main GUI after "
                       "logging in.",
                  style="Subtitle.TLabel").pack(pady=(0, 24))
        ttk.Button(outer, text="Close", style="Danger.TButton",
                   command=self.root.destroy).pack()

    def _dispatch(self):
        for w in self.root.winfo_children():
            w.destroy()
        if _is_admin_user(self.user):
            AdminDashboard(self.root, self.db, self.user, self.root.destroy)
        else:
            VoterDashboard(self.root, self.db, self.user, self.root.destroy)

    def run(self):
        self.root.mainloop()
