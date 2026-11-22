"""Active Sessions section.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    CONTENT_BG,
    TEXT_DARK,
    TEXT_LIGHT,
    TEXT_MUTED,
)


class SessionsMixin:
    # ------------------------------------------------------------------
    # Section: Active Sessions
    # ------------------------------------------------------------------

    def _build_sessions(self):
        tk.Label(
            self._content_frame, text="Active Sessions",
            font=("Segoe UI", 18, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            self._content_frame,
            text="View and manage active user sessions across all systems.",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 12))

        tree_frame = tk.Frame(self._content_frame, bg=CONTENT_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 8))

        columns = ("username", "user_id", "token_preview", "created_at", "expires_at")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)

        for col, heading, w in [
            ("username", "Username", 140),
            ("user_id", "User ID", 80),
            ("token_preview", "Token", 120),
            ("created_at", "Created", 160),
            ("expires_at", "Expires", 160),
        ]:
            tree.heading(col, text=heading)
            tree.column(col, width=w, minwidth=60)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        sessions = []
        svc = self._get_admin_service()
        if svc:
            try:
                sessions = svc.get_active_sessions()
            except Exception:
                pass

        for s in sessions:
            tree.insert("", tk.END, values=(
                s.get("username", ""),
                s.get("user_id", ""),
                s.get("token_preview", ""),
                str(s.get("created_at", ""))[:19],
                str(s.get("expires_at", ""))[:19],
            ))

        if not sessions:
            tk.Label(
                self._content_frame, text="No active sessions found.",
                font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
            ).pack(pady=8)

        # Action buttons
        action_bar = tk.Frame(self._content_frame, bg=CONTENT_BG)
        action_bar.pack(fill=tk.X, padx=24, pady=(0, 12))

        def _force_logout():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("No Selection", "Select a session first.")
                return
            vals = tree.item(sel[0], "values")
            user_id = vals[1]
            username = vals[0]
            if not messagebox.askyesno(
                "Confirm Force Logout",
                f"Force logout all sessions for '{username}' (user_id={user_id})?",
            ):
                return
            svc2 = self._get_admin_service()
            if svc2:
                try:
                    svc2.force_logout_user(int(user_id))
                    messagebox.showinfo("Done", f"All sessions for '{username}' have been terminated.")
                    self._show_section("sessions")
                except Exception as exc:
                    messagebox.showerror("Error", str(exc))

        tk.Button(
            action_bar, text="Force Logout Selected User", font=("Segoe UI", 10),
            bg="#e74c3c", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=12,
            command=_force_logout,
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            action_bar, text="Refresh", font=("Segoe UI", 10),
            bg="#3498db", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=12,
            command=lambda: self._show_section("sessions"),
        ).pack(side=tk.LEFT)
