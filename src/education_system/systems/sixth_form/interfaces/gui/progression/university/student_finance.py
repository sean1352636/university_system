"""GUI for the student-finance (SFE) checklist — the "Student finance" tab."""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.sixth_form.domain.progression.university import (
    student_finance as data,
    workflow as workflow_data,
)
from education_system.systems.sixth_form.interfaces.gui.progression import _record_tabs as rt

logger = logging.getLogger(__name__)

_FIELDS = (
    ("opened_on", "Application opened", "date"),
    ("submitted_on", "Application submitted", "date"),
    ("customer_ref", "SFE customer reference", "text"),
    ("evidence_type", "Evidence requested", "choice", data.EVIDENCE_TYPES),
    ("evidence_requested_on", "Evidence requested on", "date"),
    ("evidence_sent_on", "Evidence sent on", "date"),
    ("entitlement_on", "Entitlement letter received", "date"),
    ("course_start", "Course start date", "date"),
    ("guidance_given_on", "Guidance given on", "date"),
    ("guidance_given_by", "Guidance given by", "text"),
    ("notes", "Notes", "multiline"),
)

_TAGS = {
    "Funding confirmed": "good", "Submitted — awaiting SFE": None,
    "Evidence outstanding": "warn", "Started, not submitted": "warn",
    "Not started": "warn", "Not submitted — past apply-by date": "bad",
}


def _cycle(f) -> int:
    raw = f.get("cycle") or ""
    return int(raw) if raw.isdigit() else workflow_data.default_cycle_year()


def build_tab(gui, parent: ttk.Frame) -> None:
    cycle = workflow_data.default_cycle_year()
    kd = data.key_dates(cycle)
    ttk.Label(
        parent,
        text=(f"Cycle {cycle}: SFE applications usually open {kd['applications_open']:%d %B}; "
              f"apply by {kd['recommended_deadline']:%d %B} for money at the start of "
              f"term (or {data.SFE_PROCESSING_WEEKS} weeks before an earlier course "
              f"start); final cut-off {kd['final_deadline']:%d %B %Y}. These are the usual "
              "dates — check gov.uk each year."),
        foreground="#555", wraplength=1000, justify="left").pack(anchor="w", pady=(0, 6))

    def load(f):
        return [r.as_row() for r in data.cohort(_cycle(f), state=f.get("state") or None)]

    def edit(table):
        row = table.require()
        rec = data.get(row["student_id"], row["cycle_year"]) or {}
        rt.form_dialog(table.parent, f"Student finance — {row['student_name']}",
                       _FIELDS, rec,
                       lambda v: data.save(row["student_id"], row["cycle_year"], v),
                       table.refresh)

    def add(table):
        rt.form_dialog(
            table.parent, "Add an applicant to the checklist",
            (("student", "Student", "choice", rt.student_choices),
             ("cycle", "Cycle (entry year)", "number")) + _FIELDS,
            {"cycle": workflow_data.default_cycle_year()},
            lambda v: data.save(rt.student_id_of(v.pop("student")),
                                int(v.pop("cycle") or workflow_data.default_cycle_year()), v),
            table.refresh)

    rt.RecordTable(
        parent,
        (("student_name", "Student", 180), ("student_id", "ID", 80),
         ("opened_on", "Opened", 90), ("submitted_on", "Submitted", 90),
         ("evidence", "Evidence", 220), ("entitlement_on", "Entitlement", 90),
         ("apply_by", "Apply by", 90), ("state", "State", 240)),
        load, key="student_id",
        filters=[("cycle", "Cycle", "text", (), workflow_data.default_cycle_year()),
                 ("state", "State", "choice", data.STATES)],
        note="Everyone with a UCAS application this cycle, plus anyone added by hand.",
        tags=lambda r: _TAGS.get(r["state"]),
        actions=[("Update checklist…", edit), ("Add applicant…", add)],
        on_open=edit)


__all__ = ["build_tab"]
