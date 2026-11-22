"""Exams Office tab: special consideration applications (restricted)."""

from __future__ import annotations

import logging
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.assessment.exam_entries.exam_entries import (
    SEASONS,
)
from education_system.systems.sixth_form.domain.assessment.exams_office import (
    special_consideration as sc,
)
from education_system.systems.sixth_form.interfaces.gui.assessment.exams_office.exams_widgets import (
    guarded,
    ERROR_FG,
    FormField,
    SeriesBar,
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
        FormField("student", "Student", "combo", labels, 42),
        FormField("season", "Season", "readonly", SEASONS),
        FormField("year", "Year"),
        FormField("component_code", "Component code"),
        FormField("reason_category", "Reason", "readonly", sc.REASON_CATEGORIES, 44),
        FormField("incident_date", "Incident date"),
        FormField("details", "Details", "text"),
        FormField("evidence", "Evidence held"),
        FormField("status", "Status", "readonly", sc.STATUSES),
        FormField("submitted_date", "Submitted date"),
        FormField("board_reference", "Board reference"),
        FormField("board_outcome", "Board outcome", "readonly", sc.OUTCOMES, 40),
        FormField("outcome_date", "Outcome date"),
        FormField("allowance_pct", "Allowance % (0-5)"),
        FormField("notes", "Notes"),
    ]


def build_tab(gui, parent: ttk.Frame) -> None:
    if not sensitive_gate(parent, "exam_special_consideration", ("EXAMS",),
                          "Special consideration applications hold medical and "
                          "personal details and are restricted to the exams office."):
        return
    top = ttk.Frame(parent)
    top.pack(fill="x", pady=(0, 6))
    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(0, 6))
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    state: dict = {}

    @guarded(gui.root)
    def refresh() -> None:
        clear(holder)
        try:
            season, year = series.get()
            rows = sc.list_applications(season=season, year=year)
        except ValueError as e:
            ttk.Label(holder, text=str(e), foreground=ERROR_FG).pack(anchor="w")
            return
        state["rows"] = {a.sc_id: a for a in rows}
        state["tree"] = table(holder, [("Student", 80), ("Name", 150), ("Component", 90),
                                       ("Reason", 200), ("Status", 110), ("Submitted", 85),
                                       ("Deadline", 85), ("Late", 40), ("Outcome", 180),
                                       ("Allow %", 55)],
                              [(a.student_id, a.full_name, a.component_code,
                                a.reason_category, a.status, a.submitted_date, a.deadline,
                                "LATE" if a.late else "", a.board_outcome, a.allowance_pct)
                               for a in rows], iids=[a.sc_id for a in rows])
        gui.status_var.set(f"{len(rows)} special consideration application(s)")

    series = SeriesBar(top, on_change=refresh)

    def save(v: dict, sc_id: int | None, mapping: dict) -> None:
        v = dict(v)
        v["student_id"] = student_from_label(v.pop("student"), mapping)
        out = sc.save_application(v, sc_id=sc_id)
        log_change("exam_special_consideration", "save", student_id=out.student_id,
                   record_ref=str(out.sc_id))

    @guarded(gui.root)
    def add() -> None:
        labels, mapping = student_choices()
        season, year = series.get()
        form_dialog(gui.root, "New special consideration", _fields(labels),
                    lambda v: save(v, None, mapping), on_done=refresh,
                    initial={"season": season, "year": year, "status": "Draft",
                             "board_outcome": "Pending"},
                    note=f"Apply within {sc.SUBMIT_WITHIN_DAYS} days of the candidate's "
                         "last paper in the subject.")

    @guarded(gui.root)
    def edit() -> None:
        sid = selected_id(state["tree"], gui.root, "an application")
        if sid is None:
            return
        a = state["rows"][sid]
        labels, mapping = student_choices()
        init = vars(a).copy()
        init["student"] = a.student_id
        form_dialog(gui.root, f"Special consideration #{sid}", _fields(labels),
                    lambda v: save(v, sid, mapping), initial=init, on_done=refresh)

    @guarded(gui.root)
    def delete() -> None:
        sid = selected_id(state["tree"], gui.root, "an application")
        if sid is not None and messagebox.askyesno("Delete", "Delete this application?",
                                                   parent=gui.root):
            run_action(gui.root, lambda: sc.delete_application(sid), then=refresh)

    for label, cmd in (("New", add), ("Edit / record outcome", edit), ("Delete", delete)):
        ttk.Button(actions, text=label, command=cmd).pack(side="left", padx=(0, 6))
    refresh()
