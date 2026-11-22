"""Exams Office tab: malpractice and maladministration log (restricted)."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.assessment.exam_entries.exam_entries import (
    EXAM_BOARDS,
)
from education_system.systems.sixth_form.domain.assessment.exams_office import (
    malpractice as mp,
)
from education_system.systems.sixth_form.interfaces.gui.assessment.exams_office.exams_widgets import (
    guarded,
    FormField,
    clear,
    form_dialog,
    log_change,
    run_action,
    selected_id,
    sensitive_gate,
    student_choices,
    student_from_label,
    table,
)

logger = logging.getLogger(__name__)


def _fields(labels: list[str]) -> list[FormField]:
    return [
        FormField("subject_type", "Who", "readonly", mp.SUBJECT_TYPES),
        FormField("category", "Category", "readonly", mp.CATEGORIES),
        FormField("student", "Candidate", "combo", ["", *labels], 42),
        FormField("staff_id", "Staff ID"),
        FormField("staff_name", "Staff name"),
        FormField("incident_date", "Incident date"),
        FormField("incident_type", "Incident type", "readonly", mp.INCIDENT_TYPES, 44),
        FormField("incident", "What happened", "text"),
        FormField("sitting_id", "Sitting # (optional)"),
        FormField("exam_board", "Board", "readonly", ["", *EXAM_BOARDS]),
        FormField("component_code", "Component code"),
        FormField("jcq_form", "JCQ form", "readonly", ["", *mp.JCQ_FORMS], 44),
        FormField("form_reference", "Form reference"),
        FormField("reported_to_board_date", "Reported to board (date)"),
        FormField("board_reference", "Board reference"),
        FormField("status", "Status", "readonly", mp.STATUSES),
        FormField("outcome", "Outcome"),
        FormField("outcome_date", "Outcome date"),
        FormField("sanction", "Sanction", "combo",
                  ["", *mp.CANDIDATE_SANCTIONS, *mp.STAFF_SANCTIONS], 44),
    ]


def build_tab(gui, parent: ttk.Frame) -> None:
    if not sensitive_gate(parent, "exam_malpractice", ("EXAMS",),
                          "The malpractice log is restricted to the exams office."):
        return
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    status_var = tk.StringVar()
    ttk.Label(bar, text="Status:").pack(side="left")
    ttk.Combobox(bar, textvariable=status_var, values=["", *mp.STATUSES], state="readonly",
                 width=18).pack(side="left", padx=(4, 10))
    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(0, 6))
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    state: dict = {}

    @guarded(gui.root)
    def refresh() -> None:
        clear(holder)
        rows = mp.list_cases(status=status_var.get() or None)
        state["rows"] = {c.case_id: c for c in rows}
        state["tree"] = table(holder, [("#", 40), ("Date", 85), ("Category", 140),
                                       ("Who", 120), ("Incident", 220), ("Form", 120),
                                       ("Reported", 85), ("Status", 110), ("Outcome", 160),
                                       ("Sanction", 160)],
                              [(c.case_id, c.incident_date, c.category, c.who,
                                c.incident_type, (c.jcq_form or "").split(" (")[0],
                                c.reported_to_board_date, c.status, c.outcome, c.sanction)
                               for c in rows], iids=[c.case_id for c in rows])
        gui.status_var.set(f"{len(rows)} malpractice case(s)")

    def save(v: dict, case_id: int | None, mapping: dict) -> None:
        v = dict(v)
        stu = v.pop("student")
        v["student_id"] = student_from_label(stu, mapping) if stu else None
        out = mp.save_case(v, case_id=case_id)
        log_change("exam_malpractice", "save", student_id=out.student_id,
                   record_ref=str(out.case_id))

    @guarded(gui.root)
    def add() -> None:
        labels, mapping = student_choices()
        form_dialog(gui.root, "Log malpractice / maladministration", _fields(labels),
                    lambda v: save(v, None, mapping), on_done=refresh,
                    initial={"subject_type": "Candidate", "status": "Open"})

    @guarded(gui.root)
    def edit() -> None:
        cid = selected_id(state["tree"], gui.root, "a case")
        if cid is None:
            return
        c = state["rows"][cid]
        labels, mapping = student_choices()
        init = vars(c).copy()
        init["student"] = c.student_id or ""
        form_dialog(gui.root, f"Case #{cid}", _fields(labels),
                    lambda v: save(v, cid, mapping), initial=init, on_done=refresh)

    @guarded(gui.root)
    def delete() -> None:
        cid = selected_id(state["tree"], gui.root, "a case")
        if cid is not None and messagebox.askyesno("Delete", "Delete this case?",
                                                   parent=gui.root):
            run_action(gui.root, lambda: mp.delete_case(cid), then=refresh)

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    for label, cmd in (("Log case", add), ("Edit / record outcome", edit), ("Delete", delete)):
        ttk.Button(actions, text=label, command=cmd).pack(side="left", padx=(0, 6))
    refresh()
