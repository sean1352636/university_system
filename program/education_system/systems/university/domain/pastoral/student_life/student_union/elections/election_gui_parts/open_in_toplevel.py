"""Extracted function implementation."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def open_in_toplevel(parent, auth=None):
    """Embed the election GUI in a Toplevel of an existing Tk app.

    Used by the Student Union GUI to surface this module without
    spawning a new process. ``auth`` is the live UserAuth (or shim)
    from the host app — falls back to global auth lookup.
    """
    win = tk.Toplevel(parent)
    win.title("Student Union Election System")
    win.geometry("1200x780")
    win.minsize(900, 600)
    win.configure(bg=BG)

    db = Database()
    setup_styles()

    # Resolve user — prefer the LIVE global auth over the passed-in
    # handle. If the host GUI was opened in an earlier session, its
    # ``self.auth`` may still point at a logged-out (or even replaced)
    # auth instance, so trusting it would show "please log in" even
    # though the user has since re-authenticated. Global is the source
    # of truth that ``main_gui.set_auth`` updates on every login.
    user = None
    cu = None
    try:
        from education_system.systems.university.infrastructure.auth import (  # noqa: E501
            get_global_auth,
        )
        ga = get_global_auth()
        cu = ga.current_user if (ga and getattr(ga, 'current_user', None)) else None
    except Exception:
        cu = None
    if cu is None:
        try:
            cu = (auth.current_user
                  if (auth and getattr(auth, 'current_user', None))
                  else None)
        except Exception:
            cu = None

    if cu:
        user = {
            'id': cu.get('id') or cu.get('user_id'),
            'user_id': cu.get('user_id') or cu.get('id'),
            'username': cu.get('username', ''),
            'role': cu.get('role', ''),
            'email': cu.get('email', ''),
            'student_id': cu.get('student_id') or cu.get('username', ''),
            'name': cu.get('name') or cu.get('username', ''),
        }

    if not user:
        outer = ttk.Frame(win, style="TFrame")
        outer.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(outer, text="🔒 Authentication required",
                  style="Title.TLabel").pack(pady=(0, 6))
        ttk.Label(outer,
                  text="Log in through the main GUI to access elections.",
                  style="Subtitle.TLabel").pack(pady=(0, 24))
        ttk.Button(outer, text="Close", style="Danger.TButton",
                   command=win.destroy).pack()
        return win

    if _is_admin_user(user):
        AdminDashboard(win, db, user, win.destroy)
    else:
        VoterDashboard(win, db, user, win.destroy)
    return win
