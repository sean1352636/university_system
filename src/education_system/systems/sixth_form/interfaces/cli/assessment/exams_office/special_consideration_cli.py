"""CLI: special consideration applications (restricted)."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.assessment.exams_office import (
    special_consideration as sc,
)
from education_system.systems.sixth_form.interfaces.cli.assessment.exams_office.exams_cli_helpers import (
    ask,
    form,
    log_change,
    pause,
    pick_student,
    run_menu,
    sensitive,
    series,
    show_table,
    yes,
)

_AREA = "exam_special_consideration"

_FIELDS = [("component_code", "Component code"),
           ("reason_category", "Reason", sc.REASON_CATEGORIES),
           ("incident_date", "Incident date"), ("details", "Details"),
           ("evidence", "Evidence held"), ("status", "Status", sc.STATUSES),
           ("submitted_date", "Submitted date"), ("board_reference", "Board reference"),
           ("board_outcome", "Board outcome", sc.OUTCOMES), ("outcome_date", "Outcome date"),
           ("allowance_pct", "Allowance % (0-5)"), ("notes", "Notes")]


def list_all() -> None:
    season, year = series()
    rows = sc.list_applications(season=season, year=year)
    show_table([("#", 4), ("Student", 10), ("Component", 10), ("Reason", 24),
                ("Status", 16), ("Deadline", 10), ("Late", 4), ("Outcome", 24)],
               [(a.sc_id, a.student_id, a.component_code, a.reason_category, a.status,
                 a.deadline, "LATE" if a.late else "", a.board_outcome) for a in rows])
    pause()


def new() -> None:
    sid = pick_student()
    season, year = series()
    data = form(_FIELDS, {"status": "Draft", "board_outcome": "Pending"})
    a = sc.save_application({**data, "student_id": sid, "season": season, "year": year})
    log_change(_AREA, "save", student_id=sid, record_ref=str(a.sc_id))
    print(f"  ✓ Application #{a.sc_id} saved (deadline {a.deadline or 'unknown'})")
    pause()


def edit() -> None:
    sc_id = int(ask("Application #", required=True))
    a = sc.get_application(sc_id)
    if a is None:
        print("  No such application.")
        return
    data = form(_FIELDS, vars(a))
    sc.save_application({**data, "student_id": a.student_id, "season": a.season,
                         "year": a.year}, sc_id=sc_id)
    log_change(_AREA, "save", student_id=a.student_id, record_ref=str(sc_id))
    print("  ✓ Saved")
    pause()


def delete() -> None:
    sc_id = int(ask("Application #", required=True))
    if yes("Delete it"):
        sc.delete_application(sc_id)
        print("  ✓ Deleted")


MENU = [("List applications", list_all), ("New application", new),
        ("Edit / record outcome", edit), ("Delete", delete)]


def run() -> None:
    if sensitive(_AREA, ("EXAMS",)):
        run_menu("Special Consideration", MENU)
