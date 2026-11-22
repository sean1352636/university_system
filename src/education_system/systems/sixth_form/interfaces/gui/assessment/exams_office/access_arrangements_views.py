"""Exams Office tab: access arrangements with Form 8 evidence and expiry.

Arrangements are recorded by the SEN team (Accessibility, category
"Exam Access"); this tab only adds the exams-office evidence. Restricted
to staff with exams or SEND access, and every view is logged.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.sixth_form.domain.assessment.exams_office import (
    access_arrangements as aa,
)
from education_system.systems.sixth_form.interfaces.gui.assessment.exams_office.exams_widgets import (
    guarded,
    FormField,
    clear,
    form_dialog,
    log_change,
    selected_id,
    sensitive_gate,
    table,
)

logger = logging.getLogger(__name__)


def build_tab(gui, parent: ttk.Frame) -> None:
    if not sensitive_gate(parent, "exam_access_arrangements", ("EXAMS", "SEND"),
                          "Exam access arrangements come from SEN records and are "
                          "restricted to the exams officer and SEND staff."):
        return
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    problems_var = tk.BooleanVar(value=False)
    sid_var = tk.StringVar()
    ttk.Label(bar, text="Student:").pack(side="left")
    ttk.Entry(bar, textvariable=sid_var, width=12).pack(side="left", padx=(4, 10))
    ttk.Checkbutton(bar, text="Only expired / missing evidence / expiring",
                    variable=problems_var).pack(side="left", padx=(0, 10))
    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(0, 6))
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    ttk.Label(parent, text=(f"An approval is valid for {aa.APPROVAL_VALID_MONTHS} months. "
                            "Expired arrangements are not applied to sittings. Add or "
                            "change the arrangements themselves in Accessibility."),
              foreground="#555").pack(anchor="w", pady=(4, 0))
    state: dict = {}

    @guarded(gui.root)
    def refresh() -> None:
        clear(holder)
        if problems_var.get():
            rows = aa.expired_or_flagged()
        else:
            rows = aa.list_arrangements(student_id=sid_var.get().strip() or None)
        if sid_var.get().strip():
            rows = [a for a in rows if a.student_id == sid_var.get().strip()]
        from education_system.systems.sixth_form.domain.assessment.exams_office import store
        names = store.student_names()
        state["rows"] = {a.accommodation_id: a for a in rows}
        state["tree"] = table(holder, [("Student", 80), ("Name", 160), ("Arrangement", 180),
                                       ("Kind", 100), ("Extra %", 55), ("Form 8 ref", 100),
                                       ("Approved", 90), ("Expires", 90), ("Status", 70),
                                       ("Problem", 220)],
                              [(a.student_id, names.get(a.student_id), a.name, a.kind,
                                a.extra_time_pct or "", a.form8_reference, a.approval_date,
                                a.expiry_date, a.status, a.problem) for a in rows],
                              iids=[a.accommodation_id for a in rows])
        gui.status_var.set(f"{len(rows)} exam access arrangement(s)")

    @guarded(gui.root)
    def evidence() -> None:
        aid = selected_id(state["tree"], gui.root, "an arrangement")
        if aid is None:
            return
        a = state["rows"][aid]

        def submit(v: dict) -> None:
            aa.record_evidence(aid, v)
            log_change("exam_access_arrangements", "record_evidence",
                       student_id=a.student_id, record_ref=str(aid))

        form_dialog(gui.root, f"Form 8 evidence — {a.student_id}: {a.name}",
                    [FormField("form8_reference", "Form 8 / AAO reference"),
                     FormField("approval_date", "Approval date (YYYY-MM-DD)"),
                     FormField("expiry_date", "Expiry (blank = approval + 26 months)"),
                     FormField("approved_by", "Approved by"),
                     FormField("notes", "Notes")],
                    submit, on_done=refresh,
                    initial={"form8_reference": a.form8_reference,
                             "approval_date": a.approval_date,
                             "expiry_date": a.expiry_date, "approved_by": a.approved_by,
                             "notes": a.evidence_notes})

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    ttk.Button(actions, text="Record Form 8 evidence…", command=evidence).pack(side="left")
    refresh()
