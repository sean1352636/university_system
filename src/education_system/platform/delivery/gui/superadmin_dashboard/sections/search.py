"""Cross-system user Search section.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import tkinter as tk
from tkinter import ttk

from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    CONTENT_BG,
    SYSTEM_LABELS,
    TEXT_DARK,
    TEXT_LIGHT,
    TEXT_MUTED,
)


class SearchMixin:
    # ------------------------------------------------------------------
    # Section: Student Search
    # ------------------------------------------------------------------

    @staticmethod
    def _roles_summary(systems):
        """Render a user's system/role assignments as 'University:admin, ...'."""
        if not systems:
            return "—"
        return ", ".join(
            f"{SYSTEM_LABELS.get(s.get('system_key', ''), s.get('system_key', ''))}"
            f":{s.get('role', '')}"
            for s in systems
        )

    def _build_search(self):
        tk.Label(
            self._content_frame,
            text="Find a Person",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            self._content_frame,
            text="One box for everyone — staff/admin accounts and students across "
                 "all systems. Shows system(s), role, account status, and last login.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 12))

        # Search bar
        search_bar = tk.Frame(self._content_frame, bg=CONTENT_BG)
        search_bar.pack(fill=tk.X, padx=24, pady=(0, 8))

        search_var = tk.StringVar()
        search_entry = tk.Entry(
            search_bar, textvariable=search_var, font=("Segoe UI", 12), width=35,
        )
        search_entry.pack(side=tk.LEFT, padx=(0, 8), ipady=4)
        search_entry.focus_set()

        count_label = tk.Label(
            self._content_frame,
            text="Type a name, username, email, or student ID and press Enter.",
            font=("Segoe UI", 9), bg=CONTENT_BG, fg=TEXT_MUTED,
        )
        count_label.pack(anchor=tk.W, padx=24, pady=(0, 8))

        # Unified results treeview
        tree_frame = tk.Frame(self._content_frame, bg=CONTENT_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 12))

        columns = ("kind", "name", "ident", "where", "status", "extra")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=18)
        for col, heading, w in [
            ("kind", "Type", 70),
            ("name", "Name", 200),
            ("ident", "Username / ID", 140),
            ("where", "System(s) & Role", 260),
            ("status", "Status", 90),
            ("extra", "Last Login / Year", 150),
        ]:
            tree.heading(col, text=heading)
            tree.column(col, width=w, minwidth=50)

        tree.tag_configure("locked", foreground="#e74c3c")
        tree.tag_configure("inactive", foreground="#95a5a6")
        tree.tag_configure("student", foreground="#2c3e50")

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        def _do_search(*_args):
            query = search_var.get().strip()
            if not query or len(query) < 2:
                return
            tree.delete(*tree.get_children())
            count_label.config(text="Searching…")

            svc = self._get_admin_service()
            if not svc:
                count_label.config(text="Admin service unavailable.")
                return
            try:
                res = svc.search(query)
            except Exception as exc:
                count_label.config(text=f"Search error: {exc}")
                return

            users = res.get("users", [])
            students = res.get("students", [])

            for u in users:
                status = u.get("status", "")
                last = (u.get("last_login", "") or "")[:16] or "never"
                tag = status if status in ("locked", "inactive") else ""
                tree.insert("", tk.END, tags=(tag,), values=(
                    "User",
                    u.get("display_name") or u.get("username", ""),
                    u.get("username", ""),
                    self._roles_summary(u.get("systems", [])),
                    status,
                    last,
                ))

            for s in students:
                sys_label = SYSTEM_LABELS.get(s.get("system", ""), s.get("system", ""))
                tree.insert("", tk.END, tags=("student",), values=(
                    "Student",
                    s.get("name", ""),
                    s.get("student_id", s.get("id", "")),
                    sys_label,
                    s.get("status", ""),
                    s.get("year_group", ""),
                ))

            total = len(users) + len(students)
            if not total:
                count_label.config(text=f"No matches for “{query}”.")
            else:
                count_label.config(
                    text=f"{total} match(es): {len(users)} account(s), "
                         f"{len(students)} student record(s).")

        tk.Button(
            search_bar, text="Search", font=("Segoe UI", 11), bg="#3498db",
            fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=16, command=_do_search,
        ).pack(side=tk.LEFT)

        search_entry.bind("<Return>", _do_search)
