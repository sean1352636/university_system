"""Student-facing panels: finance, union membership, engagements."""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk


class StudentFinancePanel(ttk.Frame):
    """Inline summary of a student's balance + active holds.

    Embed in the enrolment dialog (Course/Module GUI), the resit
    confirmation (Exam GUI), or the library checkout screen so the
    operator sees money state without context-switching.

    Auto-refreshes on ``finance.charge.raised`` and ``finance.hold.changed``.
    """

    def __init__(self, master: tk.Misc, student_id: str | None = None,
                 *, listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._student_id: str | None = None

        self._heading_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.finance', default="Finance: —"))
        self._balance_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.balance', default="Balance: —"))
        self._hold_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.holds', default="Holds: —"))

        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))
        ttk.Label(self, textvariable=self._balance_var).pack(anchor="w", padx=10)
        self._hold_label = ttk.Label(self, textvariable=self._hold_var)
        self._hold_label.pack(anchor="w", padx=10, pady=(0, 6))

        cols = ("source", "reason", "amount")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=4)
        for c, w in zip(cols, (110, 320, 90)):
            self._tree.heading(c, text=c.capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.pack(fill="x", expand=False, padx=8, pady=(0, 8))

        if listen_to_events:
            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    subscribe_tk, EVENT_CHARGE_RAISED, EVENT_HOLD_CHANGED,
                )

                def _on_change(**payload):
                    if (self._student_id and
                            str(payload.get("student_id") or "") in ("", str(self._student_id))):
                        self.refresh()

                for evt in (EVENT_CHARGE_RAISED, EVENT_HOLD_CHANGED):
                    subscribe_tk(evt, self, _on_change)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        if student_id:
            self.set_student(student_id)

    def set_student(self, student_id: str) -> None:
        self._student_id = str(student_id) if student_id else None
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        if not self._student_id:
            self._heading_var.set("Finance: —")
            self._balance_var.set("Balance: —")
            self._hold_var.set("Holds: —")
            return
        self._heading_var.set(f"Finance — student {self._student_id}")

        try:
            from education_system.systems.university.services.bus.finance_bus import (
                student_balance, list_active_holds,
            )
            balance = student_balance(self._student_id)
            holds = list_active_holds(self._student_id)
        except Exception:
            balance, holds = 0.0, []

        self._balance_var.set(f"Balance: £{balance:,.2f}")

        # Meal-plan balance line (#8). Best-effort; absent service =
        # silent skip.
        try:
            from education_system.systems.university.plugins.campus_commerce.services.restaurant_bus import (
                meal_plan_balance,
            )
            mp = meal_plan_balance(self._student_id)
            if mp:
                self._balance_var.set(
                    f"Balance: £{balance:,.2f} · "
                    f"Meal plan: £{mp:,.2f}"
                )
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        if holds:
            self._hold_var.set(f"⚠ {len(holds)} active hold(s)")
            self._hold_label.configure(foreground="#c0392b")
        else:
            self._hold_var.set("✓ No active holds")
            self._hold_label.configure(foreground="#27ae60")

        for h in holds:
            self._tree.insert("", "end", values=(
                h.get("source", ""), h.get("reason", ""),
                f"£{float(h.get('amount') or 0):,.2f}",
            ))


class StudentUnionPanel(ttk.Frame):
    """Inline student-union summary: clubs, charges, advocacy.

    Embed alongside ``OpenCasesPanel`` on student profile / Grade
    Tracking views. Auto-refreshes on
    ``finance.charge.raised`` (fee posted),
    ``su.membership.changed`` (joined/left),
    and ``su.advocacy.requested`` (claimed support).
    """

    def __init__(self, master: tk.Misc,
                 student_id: str | int | None = None,
                 *, listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._student_id: str | None = None

        self._heading_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.student_union', default="Student Union"))
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        self._clubs_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.clubs', default="Clubs: —"))
        self._charges_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.outstanding_fees', default="Outstanding fees: —"))
        self._advocacy_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.advocacy', default="Advocacy: —"))
        ttk.Label(self, textvariable=self._clubs_var).pack(anchor="w", padx=10)
        ttk.Label(self, textvariable=self._charges_var).pack(anchor="w", padx=10)
        ttk.Label(self, textvariable=self._advocacy_var).pack(
            anchor="w", padx=10, pady=(0, 6),
        )

        cols = ("kind", "ref", "info", "when")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=4)
        for c, w in zip(cols, (90, 110, 240, 110)):
            self._tree.heading(c, text=c.capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        if listen_to_events:
            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    subscribe_tk,
                    EVENT_CHARGE_RAISED, EVENT_MEMBERSHIP_CHANGED,
                    EVENT_SU_ADVOCACY_REQUESTED,
                )

                def _on_change(**payload):
                    sid = payload.get("student_id")
                    if (self._student_id and
                            (sid is None or str(sid) == self._student_id)):
                        self.refresh()

                for evt in (EVENT_CHARGE_RAISED, EVENT_MEMBERSHIP_CHANGED,
                            EVENT_SU_ADVOCACY_REQUESTED):
                    subscribe_tk(evt, self, _on_change)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        if student_id is not None:
            self.set_student(student_id)

    def set_student(self, student_id: str | int) -> None:
        self._student_id = str(student_id) if student_id is not None else None
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        if not self._student_id:
            self._heading_var.set("Student Union")
            self._clubs_var.set("Clubs: —")
            self._charges_var.set("Outstanding fees: —")
            self._advocacy_var.set("Advocacy: —")
            return
        self._heading_var.set(f"Student Union — {self._student_id}")

        try:
            from education_system.systems.university.services.bus.student_union_bus import (
                list_clubs_for, list_outstanding_su_charges,
                list_advocacy_requests_for,
            )
            clubs = list_clubs_for(self._student_id)
            charges = list_outstanding_su_charges(self._student_id)
            advocacy = list_advocacy_requests_for(self._student_id)
        except Exception:
            clubs, charges, advocacy = [], [], []

        self._clubs_var.set(
            f"Clubs: {len(clubs)} active"
            + (f" — {', '.join(c.get('name') or '?' for c in clubs[:3])}"
               if clubs else "")
        )
        total = sum(float(c.get("amount") or 0) for c in charges)
        self._charges_var.set(
            f"SU charges (12mo): £{total:,.2f} across {len(charges)} item(s)"
        )
        active_adv = [a for a in advocacy if a.get("status") in ("pending", "claimed")]
        self._advocacy_var.set(
            f"Advocacy: {len(active_adv)} active request(s)"
            if active_adv else "Advocacy: none active"
        )

        for c in clubs:
            self._tree.insert("", "end", values=(
                "club",
                f"#{c.get('club_id')}",
                c.get("name") or "—",
                (c.get("join_date") or "")[:10],
            ))
        for c in charges:
            self._tree.insert("", "end", values=(
                "charge",
                c.get("reference_id") or "",
                f"£{float(c.get('amount') or 0):,.2f} — "
                f"{c.get('description') or ''}",
                (c.get("created_at") or "")[:10],
            ))
        for a in active_adv:
            self._tree.insert("", "end", values=(
                "advocacy",
                f"case #{a.get('case_id')}",
                f"{a.get('case_kind') or ''} ({a.get('status')})",
                (a.get("requested_at") or "")[:10],
            ))


class EngagementsPanel(ttk.Frame):
    """Inline view of careers engagements — jobs / internships /
    placements / apprenticeships / mentorships — for one subject.

    Works for current students (read live engagements) and alumni
    (read past engagements). Auto-refreshes on
    ``careers.engagement.started/ended`` and ``careers.hours.logged``.
    """

    _OVERDUE_FG = "#c0392b"
    _PROGRESS_FG = "#0066cc"

    def __init__(self, master: tk.Misc,
                 subject_id: str | int | None = None,
                 *, listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._subject_id: str | None = None

        self._heading_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.engagements', default="Engagements"))
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        self._summary_var = tk.StringVar(value="—")
        ttk.Label(self, textvariable=self._summary_var).pack(
            anchor="w", padx=10, pady=(0, 4),
        )

        cols = ("kind", "role", "employer", "hours", "status")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=5)
        for c, w in zip(cols, (110, 160, 160, 110, 90)):
            self._tree.heading(c, text=c.capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.tag_configure("overdue", foreground=self._OVERDUE_FG)
        self._tree.tag_configure("progressing", foreground=self._PROGRESS_FG)
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        if listen_to_events:
            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    subscribe_tk,
                    EVENT_ENGAGEMENT_STARTED, EVENT_ENGAGEMENT_ENDED,
                    EVENT_HOURS_LOGGED,
                )

                def _on_change(**payload):
                    sid = payload.get("student_id")
                    if (self._subject_id and
                            (sid is None or str(sid) == self._subject_id)):
                        self.refresh()

                for evt in (EVENT_ENGAGEMENT_STARTED,
                            EVENT_ENGAGEMENT_ENDED,
                            EVENT_HOURS_LOGGED):
                    subscribe_tk(evt, self, _on_change)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        if subject_id is not None:
            self.set_subject(subject_id)

    def set_subject(self, subject_id: str | int) -> None:
        self._subject_id = str(subject_id) if subject_id is not None else None
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        if not self._subject_id:
            self._heading_var.set("Engagements")
            self._summary_var.set("—")
            return
        self._heading_var.set(f"Engagements — {self._subject_id}")

        try:
            from education_system.systems.university.services.bus.careers_bus import (
                list_engagements,
            )
            rows = list_engagements(self._subject_id)
        except Exception as exc:
            self._summary_var.set(f"(unavailable: {exc})")
            return

        active = [r for r in rows if r.get("status") == "active"]
        self._summary_var.set(
            f"{len(rows)} engagements · {len(active)} active"
        )

        for r in rows:
            req = r.get("hours_required") or 0
            done = r.get("hours_logged") or 0
            pct = f"{(done / req * 100):.0f}%" if req > 0 else "—"
            hours_label = (
                f"{int(done)}/{int(req)}h ({pct})" if req > 0
                else (f"{int(done)}h" if done else "—")
            )
            tag = ()
            if req > 0 and done < req and r.get("status") != "active":
                tag = ("overdue",)
            elif req > 0 and 0 < done < req:
                tag = ("progressing",)

            employer = ""
            try:
                from education_system.systems.university.services.bus.careers_bus import (
                    get_employer,
                )
                emp = get_employer(r.get("employer_id")) if r.get("employer_id") else None
                if emp:
                    employer = emp.get("company_name") or ""
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

            self._tree.insert("", "end", values=(
                r.get("kind") or "",
                r.get("role") or "",
                employer,
                hours_label,
                r.get("status") or "",
            ), tags=tag)


__all__ = [
    "StudentFinancePanel",
    "StudentUnionPanel",
    "EngagementsPanel",
]
