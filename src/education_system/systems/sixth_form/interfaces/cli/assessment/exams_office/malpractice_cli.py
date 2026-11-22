"""CLI: malpractice and maladministration log (restricted)."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.assessment.exams_office import (
    malpractice as mp,
)
from education_system.systems.sixth_form.interfaces.cli.assessment.exams_office.exams_cli_helpers import (
    ask,
    form,
    log_change,
    pause,
    pick,
    run_menu,
    sensitive,
    show_table,
    yes,
)

_AREA = "exam_malpractice"

_FIELDS = [("category", "Category", mp.CATEGORIES), ("student_id", "Candidate ID"),
           ("staff_id", "Staff ID"), ("staff_name", "Staff name"),
           ("incident_date", "Incident date (YYYY-MM-DD)"),
           ("incident_type", "Incident type", mp.INCIDENT_TYPES),
           ("incident", "What happened"), ("sitting_id", "Sitting # (optional)"),
           ("component_code", "Component code"), ("jcq_form", "JCQ form", mp.JCQ_FORMS),
           ("form_reference", "Form reference"),
           ("reported_to_board_date", "Reported to board (date)"),
           ("board_reference", "Board reference"), ("status", "Status", mp.STATUSES),
           ("outcome", "Outcome"), ("outcome_date", "Outcome date"),
           ("sanction", "Sanction")]


def list_all() -> None:
    rows = mp.list_cases()
    show_table([("#", 4), ("Date", 10), ("Category", 20), ("Who", 16), ("Incident", 26),
                ("Reported", 10), ("Status", 16), ("Sanction", 24)],
               [(c.case_id, c.incident_date, c.category, c.who, c.incident_type,
                 c.reported_to_board_date, c.status, c.sanction) for c in rows])
    pause()


def new() -> None:
    who = pick("Who", list(mp.SUBJECT_TYPES))
    data = form(_FIELDS, {"status": "Open"})
    c = mp.save_case({**data, "subject_type": who})
    log_change(_AREA, "save", student_id=c.student_id, record_ref=str(c.case_id))
    print(f"  ✓ Case #{c.case_id} logged")
    pause()


def edit() -> None:
    cid = int(ask("Case #", required=True))
    c = mp.get_case(cid)
    if c is None:
        print("  No such case.")
        return
    data = form(_FIELDS, vars(c))
    mp.save_case({**data, "subject_type": c.subject_type}, case_id=cid)
    log_change(_AREA, "save", student_id=c.student_id, record_ref=str(cid))
    print("  ✓ Saved")
    pause()


def delete() -> None:
    cid = int(ask("Case #", required=True))
    if yes("Delete it"):
        mp.delete_case(cid)
        print("  ✓ Deleted")


MENU = [("List cases", list_all), ("Log a case", new),
        ("Edit / record outcome", edit), ("Delete", delete)]


def run() -> None:
    if sensitive(_AREA, ("EXAMS",)):
        run_menu("Malpractice Log", MENU)
