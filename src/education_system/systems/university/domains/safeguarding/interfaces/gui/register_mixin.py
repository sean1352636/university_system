"""Student register tab, ported from the UniGuard prototype.

The prototype kept its own roster and let staff add students to it. Here the
roster is owned by Student Records, so this is read-only: it lists active
students and joins on the number of open concerns attached to each, which is
the part that was actually useful — seeing the person rather than the case.

Selecting a student filters the Cases tab to their submissions.
"""

import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)

from education_system.systems.university.domains.safeguarding.application.api import (
    can,
    can_view_whistleblowing,
    student_register,
)
from education_system.systems.university.domains.safeguarding.interfaces.gui.widgets import (
    CANVAS_BG,
    INK,
    INK_SOFT,
    LINE,
    SURFACE,
)


class RegisterMixin:
    def _build_register_tab(self, host):
        # Role check only, deliberately not require(): this tab shows student
        # directory fields plus an open-concern count, never case content, so
        # it must not trip the sensitive-field policy that guards case summaries.
        # Opening a case from here still goes through the Cases tab's own gate.
        if not can(self.user, "view_case"):
            tk.Label(
                host,
                text=_t(
                    "gui.safeguarding.register.labels.no_permission",
                    default="Your role cannot view the student register.",
                ),
                bg=CANVAS_BG,
                fg=INK_SOFT,
                padx=16,
                pady=16,
            ).pack(anchor="w")
            return

        bar = tk.Frame(host, bg=CANVAS_BG)
        bar.pack(fill="x", padx=12, pady=(12, 8))
        tk.Label(
            bar,
            text=_t("gui.safeguarding.register.labels.search", default="Search"),
            bg=CANVAS_BG,
            fg=INK_SOFT,
        ).pack(side="left")
        self.register_search = ttk.Entry(bar, width=32)
        self.register_search.pack(side="left", padx=(6, 8))
        self.register_search.bind("<Return>", lambda _e: self._refresh_register())
        ttk.Button(
            bar,
            text=_t("gui.safeguarding.register.buttons.find", default="Find"),
            command=self._refresh_register,
        ).pack(side="left")
        ttk.Button(
            bar,
            text=_t("gui.safeguarding.register.buttons.clear", default="Clear"),
            command=self._clear_register_search,
        ).pack(side="left", padx=(6, 0))

        self.register_count = tk.Label(bar, text="", bg=CANVAS_BG, fg=INK_SOFT)
        self.register_count.pack(side="right")

        tk.Label(
            host,
            text=_t(
                "gui.safeguarding.register.labels.hint",
                default=(
                    "Active students from Student Records, with their count of "
                    "open concerns. Double-click a student to see their cases."
                ),
            ),
            bg=CANVAS_BG,
            fg=INK_SOFT,
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 6))

        holder = tk.Frame(
            host, bg=SURFACE, highlightbackground=LINE, highlightthickness=1
        )
        holder.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        columns = ("ref", "name", "course", "year", "email", "concerns")
        self.register_tree = ttk.Treeview(
            holder, columns=columns, show="headings", selectmode="browse"
        )
        for col, text, width in (
            ("ref", _t("gui.safeguarding.register.columns.student_id", default="Student ID"), 110),
            ("name", _t("gui.safeguarding.register.columns.name", default="Name"), 170),
            ("course", _t("gui.safeguarding.register.columns.course", default="Course"), 190),
            ("year", _t("gui.safeguarding.register.columns.year", default="Year"), 50),
            ("email", _t("gui.safeguarding.register.columns.email", default="Email"), 210),
            ("concerns", _t("gui.safeguarding.register.columns.concerns", default="Open concerns"), 100),
        ):
            self.register_tree.heading(col, text=text)
            self.register_tree.column(col, width=width, anchor="w")

        # One highlight only, and it means the same as everywhere else in the
        # portal: this person has something open against them.
        self.register_tree.tag_configure("has_concerns", background="#fdf3dd")

        scroll = ttk.Scrollbar(
            holder, orient="vertical", command=self.register_tree.yview
        )
        self.register_tree.configure(yscrollcommand=scroll.set)
        self.register_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.register_tree.bind("<Double-1>", self._open_register_selection)

        self._refresh_register()

    def _clear_register_search(self):
        self.register_search.delete(0, "end")
        self._refresh_register()

    def _refresh_register(self):
        # __dict__, not hasattr — tk.Misc.__getattr__ recurses on a missing
        # attribute when the portal is embedded.
        if "register_tree" not in self.__dict__:
            return
        needle = self.register_search.get().strip()
        try:
            rows = student_register(
                needle, include_whistleblowing=can_view_whistleblowing(self.user)
            )
        except Exception:
            logger.warning("student register refresh failed", exc_info=True)
            rows = []

        self.register_tree.delete(*self.register_tree.get_children())
        self._register_usernames = {}
        for sid, name, course, year, email, username, concerns in rows:
            iid = str(sid)
            self._register_usernames[iid] = username
            self.register_tree.insert(
                "",
                "end",
                iid=iid,
                values=(sid, name, course, year, email, concerns or ""),
                tags=("has_concerns",) if concerns else (),
            )
        # No placeholder in the locale string — a mismatched {name} in a
        # translated JSON raises inside the caller rather than here.
        label = _t("gui.safeguarding.register.labels.students", default="students")
        self.register_count.config(text=f"{len(rows)} {label}")

    def _open_register_selection(self, _event=None):
        selection = self.register_tree.selection()
        if not selection:
            return
        username = (self.__dict__.get("_register_usernames") or {}).get(selection[0])
        if not username:
            return
        # Hand off to the Cases tab, filtered to this person.
        self._filter_cases_to_username(username)


__all__ = ["RegisterMixin"]
