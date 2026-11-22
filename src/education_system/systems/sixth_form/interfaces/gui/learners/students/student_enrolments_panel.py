"""The student profile's Enrolment section, the ILR withdrawal-reason
part of the leaving form, and what happens to enrolments when a leaver
comes back on roll."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolments as enrol_data,
)
from education_system.systems.sixth_form.domain.learners.students import students as data
from education_system.systems.sixth_form.interfaces.gui.admissions.enrolments.enrolment_withdraw_dialog import (  # noqa: E501
    reason_choices,
    reason_code,
)

logger = logging.getLogger(__name__)

#: Default ILR withdrawal reason for each leaving reason on the form.
LEAVING_TO_ILR: dict[str, str] = {
    "Withdrew": "98",
    "Excluded": "46",
    "Health / Personal": "44",
    "Other": "97",
    "Completed Course": "98",
}


def _enrol_views():
    from education_system.systems.sixth_form.interfaces.gui.admissions.enrolments import (
        enrolment_views,
    )
    return enrolment_views


def _record_actions():
    from education_system.systems.sixth_form.interfaces.gui.admissions.enrolments import (
        enrolment_record_actions,
    )
    return enrolment_record_actions


def enrolment_section(gui, box: ttk.Frame, student_id: str,
                      after: Callable[[], None]) -> ttk.Treeview | None:
    """Every enrolment of the learner (status, year, tutor group), with
    Enrol / Withdraw / Reinstate for staff who manage enrolments."""
    try:
        rows = enrol_data.list_enrolments(student_id=student_id)
    except Exception as exc:  # noqa: BLE001 — shown in place
        logger.exception("Enrolments for %s not read", student_id)
        ttk.Label(box, text=f"Enrolments not read: {exc}", foreground="#a33").pack(anchor="w")
        rows = []
    tree = None
    if rows:
        tree = ttk.Treeview(box, columns=("id", "year", "yg", "tutor", "start", "status"),
                            show="headings", height=min(5, len(rows)))
        for col, text, width in (("id", "#", 50), ("year", "Year", 90),
                                 ("yg", "Year group", 80), ("tutor", "Tutor group", 100),
                                 ("start", "Start", 100), ("status", "Status", 320)):
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        for e in rows:
            status = e.status
            if e.status == "Withdrawn":
                status += (f" {e.withdrawal_date or ''} "
                           f"({e.withdrawal_reason_label or 'no reason'})")
            tree.insert("", "end", iid=str(e.enrolment_id), values=(
                e.enrolment_id, e.academic_year, f"Year {e.year_group}",
                e.tutor_group or "—", e.start_date or "—", status))
        tree.pack(anchor="w", fill="x")
    else:
        ttk.Label(box, text="No enrolments yet.", foreground="#777").pack(anchor="w")

    write = "normal" if enrol_data.can_write() else "disabled"

    def selected() -> int | None:
        sel = tree.selection() if tree is not None else ()
        if not sel:
            messagebox.showinfo("Enrolment", "Select an enrolment first.",
                                parent=gui.root)
            return None
        return int(sel[0])

    def withdraw() -> None:
        eid = selected()
        if eid is not None:
            _record_actions()._confirm_and_withdraw(gui, eid, after)

    def reinstate() -> None:
        eid = selected()
        if eid is not None:
            _record_actions().reinstate_with_reason(gui, eid, after)

    def open_selected() -> None:
        eid = selected()
        if eid is not None:
            _enrol_views().open_profile(gui, eid)

    bar = ttk.Frame(box)
    bar.pack(anchor="w", pady=(4, 0))
    ttk.Button(bar, text="Enrol…", state=write,
               command=lambda: _enrol_views().open_enrolment_from_student_profile(
                   gui, student_id)).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Withdraw…", state=write, command=withdraw
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Reinstate…", state=write, command=reinstate
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Open Enrolment", command=open_selected
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Enrolment History",
               command=lambda: _enrol_views().open_student_enrolment_history(
                   gui, student_id)).pack(side="left")
    from education_system.systems.sixth_form.interfaces.gui.admissions.enrolments.enrolment_history_views import (  # noqa: E501
        leaver_effects_section,
    )
    leaver_effects_section(box, student_id, height=4)
    return tree


def offer_reinstate_enrolment(gui, student_id: str, name: str,
                              after: Callable[[], None]) -> bool:
    """After a leaver is put back on roll: when they have a withdrawn
    enrolment for the current academic year, offer to reinstate it (aims
    reopened) instead of adding a new one. True when it was offered."""
    try:
        year = enrol_data.current_academic_year()
        withdrawn = [e for e in enrol_data.list_enrolments(
            student_id=student_id, academic_year=year) if e.status == "Withdrawn"]
    except Exception:  # noqa: BLE001 — fall back to the plain message
        logger.exception("Enrolments for %s not read", student_id)
        return False
    if not withdrawn:
        return False
    e = withdrawn[0]
    if not enrol_data.can_write():
        messagebox.showinfo(
            "Reinstated",
            f"{name} is back on roll. Their {year} enrolment (#{e.enrolment_id}) "
            "is still withdrawn — ask someone who manages enrolments to "
            "reinstate it.", parent=gui.root)
        return True
    if messagebox.askyesno(
            "Reinstate enrolment?",
            f"{name} is back on roll. Their login and tutor group have been "
            f"restored where possible.\n\nThey have a withdrawn {year} enrolment "
            f"(#{e.enrolment_id}, Year {e.year_group}, withdrawn "
            f"{e.withdrawal_date or '?'}). Reinstate it now? Its learning aims "
            "are reopened.", parent=gui.root):
        _record_actions().reinstate_with_reason(gui, e.enrolment_id, after)
    return True


# ── Leaving form: ILR reason and what happened ──────────────────────

class IlrReasonField:
    """ILR withdrawal-reason picker for the leaving form; follows the
    leaving reason until the user picks one themselves."""

    def __init__(self, parent, reason_var: tk.StringVar) -> None:
        self.var = tk.StringVar()
        self.touched = False
        self.combo = ttk.Combobox(parent, textvariable=self.var, values=reason_choices(),
                                  state="readonly", width=58)
        self.combo.bind("<<ComboboxSelected>>", lambda _e: setattr(self, "touched", True))
        self._reason_var = reason_var
        reason_var.trace_add("write", lambda *_a: self._follow())
        self._follow()

    def _follow(self) -> None:
        if self.touched:
            return
        code = LEAVING_TO_ILR.get(self._reason_var.get(), "98")
        self.var.set(next((c for c in reason_choices() if reason_code(c) == code), ""))

    @property
    def code(self) -> str | None:
        return reason_code(self.var.get()) or None


def history_marker(student_id: str) -> int:
    """The newest record-history id, to find what a change added."""
    try:
        rows = data.list_history(student_id, limit=1)
        return int(rows[0]["history_id"]) if rows else 0
    except Exception:  # noqa: BLE001
        logger.exception("History of %s not read", student_id)
        return 0


def leaving_outcome(student_id: str, since: int) -> list[str]:
    """The enrolment lines ``withdraw_student`` recorded (enrolments
    withdrawn / completed, leaver steps, problems)."""
    try:
        rows = data.list_history(student_id, limit=100)
    except Exception:  # noqa: BLE001
        logger.exception("History of %s not read", student_id)
        return []
    return [r["note"] for r in reversed(rows)
            if r["history_id"] > since and r["field"] == "Enrolment" and r.get("note")]
