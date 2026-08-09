"""Admin users — how college records connect to shared-auth accounts.

Accounts themselves live in the platform's shared ``auth.db`` and are managed
by the launcher, not here. What *is* this system's business is the join: a
signed-in account is matched to a staff or learner record by email, and when
that match fails the person gets a working login with an empty marking queue
and no timetable. This screen makes the join visible and repairable.
"""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "Users & access"


def open_window(host) -> None:
    Screen(host)


class Screen:
    def __init__(self, host):
        self.host = host
        self.ctl = host.ctl
        host.clear_content()
        parent = host.content_frame

        w.page_header(
            parent, TITLE,
            "Accounts are managed by the launcher's shared authentication. "
            "This screen shows how they resolve to college records.",
            actions=[("↻ Refresh", self.refresh)],
        )

        self.session_holder = ttk.Frame(parent)
        self.session_holder.pack(fill="x", pady=(0, 10))

        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)
        self.staff_tab = ttk.Frame(notebook, padding=8)
        self.learner_tab = ttk.Frame(notebook, padding=8)
        notebook.add(self.staff_tab, text="Staff accounts")
        notebook.add(self.learner_tab, text="Learner accounts")

        self.staff_table = w.DataTable(self.staff_tab, [
            ("id", "Staff ID", 90),
            ("name", "Name", 190),
            ("role", "Role", 165),
            ("email", "Email (the join key)", 250),
            ("contract", "Contract", 100),
            ("account", "Sign-in", 140),
        ], height=13)
        w.button_bar(self.staff_tab, [
            ("Use this staff record for my session", self.rebind_staff),
        ])

        self.learner_table = w.DataTable(self.learner_tab, [
            ("id", "Student ID", 95),
            ("name", "Name", 190),
            ("status", "Status", 95),
            ("email", "Email (the join key)", 260),
            ("group", "Tutor group", 110),
            ("account", "Sign-in", 140),
        ], height=13)
        w.button_bar(self.learner_tab, [
            ("Use this learner record for my session", self.rebind_student),
        ])
        self.refresh()

    # ── Data ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._refresh_session()
        try:
            self._refresh_staff()
            self._refresh_learners()
        except Exception as exc:
            logger.exception("Could not load FE College user data")
            w.error(self.host, TITLE, f"Could not load user data: {exc}")

    def _refresh_session(self) -> None:
        w.clear(self.session_holder)
        identity = self.ctl.identity
        linked = identity.staff or identity.student
        rows = [
            ("Signed in as", identity.username or "—"),
            ("Display name", identity.display_name),
            ("Launcher role", f"{identity.role} → {identity.view} view"),
            ("Account email", identity.email or "— (no email on the account)"),
            (
                "College record",
                (
                    f"{identity.staff.display_name}" if identity.staff
                    else f"{identity.student.display_name}" if identity.student
                    else "not linked"
                ),
                "good" if linked else "warn",
            ),
        ]
        w.kv_panel(self.session_holder, "This session", rows).pack(fill="x")

        if not linked:
            ttk.Label(
                self.session_holder,
                text=(
                    "This account has no matching college record, so "
                    "role-specific screens will be empty. Records are matched "
                    "by email — either set the account's email to match a "
                    "record below, or link one for this session."
                ),
                foreground=w.TONE["warn"], wraplength=900, justify="left",
            ).pack(anchor="w", pady=(6, 0))

    def _refresh_staff(self) -> None:
        identity = self.ctl.identity
        rows = []
        for member in self.ctl.staff.search():
            is_me = identity.staff and identity.staff.staff_id == member.staff_id
            rows.append({
                "id": member.staff_id,
                "name": member.full_name,
                "role": member.role,
                "email": member.email,
                "contract": member.employment_status,
                "account": "this session" if is_me else "—",
                "_tone": "good" if is_me else ("muted" if not member.is_active else "plain"),
                "_obj": member,
            })
        self.staff_table.set_rows(rows)

    def _refresh_learners(self) -> None:
        identity = self.ctl.identity
        rows = []
        for learner in self.ctl.students.search():
            is_me = identity.student and identity.student.student_id == learner.student_id
            rows.append({
                "id": learner.student_id,
                "name": learner.full_name,
                "status": learner.status,
                "email": learner.email or "— (cannot be matched)",
                "group": learner.tutor_group or "—",
                "account": "this session" if is_me else "—",
                "_tone": (
                    "good" if is_me
                    else "warn" if not learner.email
                    else "plain"
                ),
                "_obj": learner,
            })
        self.learner_table.set_rows(rows)

    # ── Actions ────────────────────────────────────────────────────────────

    def rebind_staff(self) -> None:
        member = self.staff_table.require_selection("a staff record")
        if member is None:
            return
        if not w.confirm(
            self.host, "Link staff record",
            f"Use {member.display_name} as the college record for this "
            "session?\n\nThe link lasts until you sign out. To make it "
            f"permanent, set the account's email to {member.email}.",
        ):
            return
        self.ctl.rebind_staff(member.staff_id)
        self.host.refresh_identity()
        self.refresh()

    def rebind_student(self) -> None:
        learner = self.learner_table.require_selection("a learner record")
        if learner is None:
            return
        if not w.confirm(
            self.host, "Link learner record",
            f"Use {learner.display_name} as the college record for this "
            "session?\n\nThe link lasts until you sign out.",
        ):
            return
        self.ctl.rebind_student(learner.student_id)
        self.host.refresh_identity()
        self.refresh()


__all__ = ["TITLE", "Screen", "open_window"]
