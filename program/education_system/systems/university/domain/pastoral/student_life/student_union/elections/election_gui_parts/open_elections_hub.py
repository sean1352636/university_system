"""Extracted function implementation."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def open_elections_hub(parent, auth=None, tool_handlers=None):
    """All Student Union election features behind a single window.

    Replaces the previous sprawl of 11 sidebar buttons. Tab 1 is the
    polished voter / admin dashboard; subsequent tabs each launch one
    of the existing specialised dialogs (Candidate Profiles, Ranked
    Choice Voting, Election Accessibility, Setup Election, Campaign
    Expenses / Compliance, Election Security, Vote Integrity, Manage /
    Configure Voting Methods).

    Parameters
    ----------
    parent : tk.Misc
        Owner widget (typically the Student Union root).
    auth : optional
        Pass-through auth handle. Used for role gating; we still
        prefer the live ``get_global_auth()`` over this so a
        re-logged-in session is honoured.
    tool_handlers : list[tuple[str, str, str|None, callable]]
        ``(label, icon, role_filter, callback)`` per tool tab.
        ``role_filter`` is ``None`` (all roles), ``'admin'``, or
        ``'staff'`` (where staff also implies admin).
    """
    # Resolve user — same priority order as open_in_toplevel: live
    # global wins over a stale handle.
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

    win = tk.Toplevel(parent)
    win.title("Student Union Elections Hub")
    win.geometry("1280x820")
    win.minsize(1000, 650)
    win.configure(bg=BG)

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

    db = Database()
    setup_styles()

    role = (user.get('role') or '').lower()
    is_admin = _is_admin_user(user)
    is_staff = role in ('admin', 'superadmin', 'staff')

    notebook = ttk.Notebook(win)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)

    # Tab 1 — the polished voter/admin dashboard, embedded into a
    # tab frame instead of given a whole window. AdminDashboard /
    # VoterDashboard don't touch root.title/geometry, so passing a
    # frame as their root is safe.
    dashboard_tab = ttk.Frame(notebook, style="TFrame")
    notebook.add(dashboard_tab,
                 text=("🛡 Admin Dashboard" if is_admin
                       else "🗳 Voter Dashboard"))
    if is_admin:
        AdminDashboard(dashboard_tab, db, user, win.destroy)
    else:
        VoterDashboard(dashboard_tab, db, user, win.destroy)

    # Tabs 2..N — one per specialised tool. Each tab is a frame with
    # a description + launch button; clicking the button opens the
    # existing dialog as a Toplevel (we don't refactor ten dialog
    # classes to embed inline; the launch-button pattern keeps the
    # consolidation cheap and the existing dialogs unchanged).
    for label, icon, role_filter, callback in (tool_handlers or []):
        if role_filter == 'admin' and not is_admin:
            continue
        if role_filter == 'staff' and not is_staff:
            continue

        tab = ttk.Frame(notebook, style="TFrame", padding=24)
        notebook.add(tab, text=f"{icon} {label}" if icon else label)

        card = tk.Frame(tab, bg=CARD, padx=32, pady=28,
                        highlightbackground="#e2e8f0",
                        highlightthickness=1)
        card.place(relx=0.5, rely=0.4, anchor="center")

        tk.Label(card, text=f"{icon}  {label}", bg=CARD, fg=PRIMARY,
                 font=("Segoe UI", 18, "bold")).pack(pady=(0, 10))
        tk.Label(card,
                 text=f"Open the {label} tool in its own window.",
                 bg=CARD, fg=MUTED,
                 font=("Segoe UI", 10)).pack(pady=(0, 20))

        def _launch(cb=callback, name=label):
            try:
                cb()
            except Exception as e:
                messagebox.showerror(
                    name, f"Could not open {name}:\n{e}",
                    parent=win)
        ttk.Button(card, text=f"Open {label}",
                   style="Primary.TButton",
                   command=_launch).pack()

    return win
