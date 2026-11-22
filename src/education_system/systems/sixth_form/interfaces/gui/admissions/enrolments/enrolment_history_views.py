"""A learner's enrolment history (every enrolment, archived ones marked)
and the persistent enrolment audit trail (``enrolment_history``)."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data

from .enrolment_common import _clear, _heading, back_to_directory

logger = logging.getLogger(__name__)

AUDIT_COLS = (("at", "When", 140), ("enrolment", "#", 50),
              ("action", "Action", 120), ("by", "By", 100),
              ("detail", "Detail", 520))


def audit_table(parent, rows: list[dict], *, height: int = 8,
                show_enrolment: bool = True) -> ttk.Treeview:
    """The audit trail rows (newest first) as a table packed into
    ``parent``."""
    cols = [c for c in AUDIT_COLS if show_enrolment or c[0] != "enrolment"]
    holder = ttk.Frame(parent)
    holder.pack(anchor="w", fill="both", expand=True)
    tree = ttk.Treeview(holder, columns=[c for c, _t, _w in cols],
                        show="headings", height=height)
    for col, text, width in cols:
        tree.heading(col, text=text)
        tree.column(col, width=width, anchor="w")
    sb = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    for r in rows:
        values = {"at": r.get("changed_at") or "", "enrolment": r.get("enrolment_id"),
                  "action": r.get("action") or "", "by": r.get("changed_by") or "—",
                  "detail": (r.get("detail") or "").replace("\n", " ")}
        tree.insert("", "end", values=[values[c] for c, _t, _w in cols])
    return tree


EFFECT_COLS = (("left", "Left on", 90), ("area", "Area", 110),
               ("label", "What", 260), ("action", "Done when they left", 340),
               ("returned", "Returned", 140))


def leaver_effects(student_id: str) -> list[dict]:
    """What leaving did to the learner's class groups, exam entries,
    bursary and meals (``leaver_effects.effects_for``), newest first."""
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        leaver_effects as _effects,
    )
    return _effects.effects_for(student_id)


def leaver_effects_section(parent, student_id: str, *, height: int = 5) -> None:
    """A "When they left" table, or nothing when there are no effects."""
    try:
        rows = leaver_effects(student_id)
    except Exception as exc:  # noqa: BLE001 — shown in place
        logger.exception("Leaver effects for %s not read", student_id)
        ttk.Label(parent, text=f"Leaver effects not read: {exc}",
                  foreground="#a33").pack(anchor="w")
        return
    if not rows:
        return
    ttk.Label(parent, text="When they left", font=("", 11, "bold")).pack(
        anchor="w", pady=(10, 2))
    tree = ttk.Treeview(parent, columns=[c for c, _t, _w in EFFECT_COLS],
                        show="headings", height=min(height, len(rows)))
    for col, text, width in EFFECT_COLS:
        tree.heading(col, text=text)
        tree.column(col, width=width, anchor="w")
    for r in rows:
        tree.insert("", "end", values=(
            r.get("left_on") or "", r.get("area") or "", r.get("label") or "",
            r.get("action") or "", r.get("returned_at") or "—"))
    tree.pack(anchor="w", fill="x")


def _show_current_year_group_chip(parent, student_id: str) -> None:
    """Feature #47 — surface the student's current year-group label."""
    label = data.current_year_group_label(student_id)
    text = label or "Not currently enrolled"
    tk.Label(parent, text=text, fg="white",
             bg="#2a7aa1" if label else "#888888",
             padx=8, pady=2).pack(anchor="w", pady=(4, 0))


def open_student_enrolment_history(gui, student_id: str) -> None:
    """Feature #17 — every enrolment for one student, newest first,
    archived ones included (marked), then the audit trail."""
    from .enrolment_views import open_profile, open_reenrol_student

    frame = _clear(gui)
    student = student_data.get_student(student_id)
    name = student.full_name if student else "(unknown)"
    _heading(frame, f"Enrolment History — {student_id} · {name}")
    _show_current_year_group_chip(frame, student_id)

    bar = ttk.Frame(frame)
    bar.pack(side="bottom", anchor="w", pady=(12, 0))

    try:
        rows = data.list_enrolments(student_id=student_id, include_archived=True)
        trail = data.enrolment_history(student_id=student_id)
    except Exception as exc:  # noqa: BLE001 — shown
        logger.exception("History for %s not read", student_id)
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        rows, trail = [], []

    tree = None
    if not rows:
        ttk.Label(frame, text="No enrolments on record for this student.",
                  foreground="#555").pack(anchor="w", pady=(8, 0))
    else:
        cols = ("enrolment_id", "academic_year", "year_group",
                "tutor_group", "start_date", "status", "detail")
        tree = ttk.Treeview(frame, columns=cols, show="headings",
                            height=min(8, len(rows)))
        for col, (text, w) in {
            "enrolment_id": ("#", 50), "academic_year": ("Year", 90),
            "year_group": ("YG", 50), "tutor_group": ("Tutor", 80),
            "start_date": ("Start", 110), "status": ("Status", 150),
            "detail": ("Withdrawal / archive", 460),
        }.items():
            tree.heading(col, text=text)
            tree.column(col, width=w, anchor="w")
        tree.tag_configure("Withdrawn", foreground="#888888")
        tree.tag_configure("Pending", foreground="#b8860b")
        tree.tag_configure("Completed", foreground="#2a7aa1")
        tree.tag_configure("archived", foreground="#999")
        tree.pack(anchor="w", pady=(8, 0), fill="x")
        for e in rows:
            detail = []
            if e.status == "Withdrawn":
                detail.append(f"withdrawn {e.withdrawal_date or '?'} "
                              f"({e.withdrawal_reason_label or 'no reason'})")
            if e.is_archived:
                detail.append(f"archived {e.archived_at}"
                              + (f": {e.archived_reason}" if e.archived_reason else ""))
            tree.insert("", "end", iid=str(e.enrolment_id),
                        tags=("archived",) if e.is_archived else (e.status,),
                        values=(e.enrolment_id, e.academic_year, e.year_group,
                                e.tutor_group or "—", e.start_date or "—",
                                f"{e.status} (archived)" if e.is_archived else e.status,
                                "; ".join(detail)))
        tree.bind("<Double-1>", lambda _e: tree.selection() and open_profile(
            gui, int(tree.selection()[0])))

    leaver_effects_section(frame, student_id)
    ttk.Label(frame, text="Audit trail", font=("", 11, "bold")).pack(
        anchor="w", pady=(12, 2))
    if trail:
        audit_table(frame, trail, height=10)
    else:
        ttk.Label(frame, text="No changes recorded yet.",
                  foreground="#777").pack(anchor="w")

    ttk.Button(bar, text="Re-enrol",
               command=lambda: open_reenrol_student(gui, student_id),
               state="normal" if data.can_write() else "disabled"
               ).pack(side="left", padx=(0, 6))
    if tree is not None:
        ttk.Button(bar, text="Open Selected",
                   command=lambda: tree.selection() and open_profile(
                       gui, int(tree.selection()[0]))
                   ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Back to Directory",
               command=lambda: back_to_directory(gui)).pack(side="left")
    gui.status_var.set(f"History for {student_id}")
