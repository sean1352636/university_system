"""CLI: exam access arrangements, Form 8 evidence and expiry (restricted)."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.assessment.exams_office import (
    access_arrangements as aa,
)
from education_system.systems.sixth_form.interfaces.cli.assessment.exams_office.exams_cli_helpers import (
    ask,
    form,
    log_change,
    pause,
    run_menu,
    sensitive,
    show_table,
)

_AREA = "exam_access_arrangements"


def _show(rows) -> None:
    show_table([("ID", 4), ("Student", 10), ("Arrangement", 22), ("Extra", 5),
                ("Form 8", 12), ("Approved", 10), ("Expires", 10), ("Problem", 30)],
               [(a.accommodation_id, a.student_id, a.name, a.extra_time_pct or "",
                 a.form8_reference, a.approval_date, a.expiry_date, a.problem)
                for a in rows])


def list_all() -> None:
    sid = ask("Student ID (blank = all)")
    _show(aa.list_arrangements(student_id=sid or None))
    pause()


def problems() -> None:
    print(f"\n  Approvals last {aa.APPROVAL_VALID_MONTHS} months; expired ones are not "
          "applied to sittings.")
    _show(aa.expired_or_flagged())
    pause()


def evidence() -> None:
    aid = int(ask("Arrangement ID", required=True))
    current = next((a for a in aa.list_arrangements(active_only=False)
                    if a.accommodation_id == aid), None)
    data = form([("form8_reference", "Form 8 / AAO reference"),
                 ("approval_date", "Approval date (YYYY-MM-DD)"),
                 ("expiry_date", "Expiry (blank = approval + 26 months)"),
                 ("approved_by", "Approved by"), ("notes", "Notes")],
                {"form8_reference": current.form8_reference,
                 "approval_date": current.approval_date,
                 "approved_by": current.approved_by} if current else None)
    a = aa.record_evidence(aid, data)
    log_change(_AREA, "record_evidence", student_id=a.student_id, record_ref=str(aid))
    print(f"  ✓ Saved — expires {a.expiry_date or '(no date)'}")
    pause()


def candidate() -> None:
    sid = ask("Student ID", required=True)
    arr = aa.for_student(sid)
    print(f"\n  {sid}: {arr.summary() or '(no exam access arrangements)'}")
    pause()


MENU = [("All arrangements", list_all), ("Expired / missing evidence / expiring", problems),
        ("Record Form 8 evidence", evidence), ("What applies to a candidate", candidate)]


def run() -> None:
    if sensitive(_AREA, ("EXAMS", "SEND")):
        run_menu("Access Arrangements", MENU)
