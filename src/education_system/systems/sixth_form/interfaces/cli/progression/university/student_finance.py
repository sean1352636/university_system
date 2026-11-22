"""CLI for the student-finance (SFE) checklist."""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domain.progression.university import (
    student_finance as data,
    workflow as workflow_data,
)
from education_system.systems.sixth_form.interfaces.cli.progression import _record_menus as rm

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
    ("notes", "Notes", "text"),
)


def _cycle() -> int:
    return rm.ask_int("Cycle (entry year)", default=workflow_data.default_cycle_year()) \
        or workflow_data.default_cycle_year()


def checklist() -> None:
    cycle = _cycle()
    rm.print_table([r.as_row() for r in data.cohort(cycle)],
                   (("student_name", "Student", 22), ("opened_on", "Opened", 10),
                    ("submitted_on", "Submitted", 10), ("evidence", "Evidence", 24),
                    ("apply_by", "Apply by", 10), ("state", "State", 34)))
    rm.pause()


def update() -> None:
    sid = rm.pick_student()
    cycle = _cycle()
    current = data.get(sid, cycle) or {}
    values = rm.form(_FIELDS, current)
    rec = data.save(sid, cycle, values)
    print(f"  ✓ Saved. Apply by {data.apply_by(cycle, rec.get('course_start'))}.")
    rm.pause()


def key_dates() -> None:
    cycle = _cycle()
    for label, d in data.key_dates(cycle).items():
        print(f"  {label.replace('_', ' '):<24} {d:%d %B %Y}")
    print("\n  These are the usual dates — check gov.uk/student-finance each year.")
    rm.pause()


MENU = (
    ("Checklist — every applicant", checklist),
    ("Update one applicant's checklist", update),
    ("Key dates", key_dates),
)


def run() -> None:
    rm.run_menu("Student finance (SFE)", MENU)


__all__ = ["run", "MENU"]
