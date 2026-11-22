"""Student self-service CLI: My Attendance, My Mitigating Circumstances,
My Parking and My Placement — the CLI twins of the windows in
shell/gui/main/features/student_self_service_gui.py.

The student id is always the signed-in student's (resolved by username); it
is never asked for, so these menus cannot show anyone else's records.
"""

from __future__ import annotations

import logging
from contextlib import closing
from datetime import date

logger = logging.getLogger(__name__)


def _pause() -> None:
    input("\nPress Enter to continue...")


def _header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _student(auth):
    """The signed-in Student, or None after printing why."""
    from education_system.systems.university.application.self_service.identity import (
        SelfServiceError,
        require_student,
        session_user,
    )
    from education_system.systems.university.infrastructure.database.db import get_connection
    try:
        with closing(get_connection()) as conn:
            return require_student(conn, session_user(auth))
    except SelfServiceError as exc:
        print(f"\n  {exc}")
        _pause()
        return None


def _table(rows: list[dict], columns: list[tuple[str, str, int]], empty: str) -> None:
    if not rows:
        print(f"  {empty}")
        return
    print("  " + "".join(label.ljust(width) for _k, label, width in columns))
    print("  " + "-" * sum(w for _k, _l, w in columns))
    for row in rows:
        cells = []
        for key, _label, width in columns:
            value = row.get(key)
            text = "—" if value is None else (f"{value:g}" if isinstance(value, float) else str(value))
            cells.append(text[: width - 1].ljust(width))
        print("  " + "".join(cells))


# ----------------------------------------------------------------------
# My Attendance
# ----------------------------------------------------------------------

def run_my_attendance(auth) -> None:
    from education_system.systems.university.application.self_service.attendance import (
        certify_own_absence,
        my_attendance,
    )
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
        transaction,
    )
    student = _student(auth)
    if student is None:
        return
    while True:
        with closing(get_connection()) as conn:
            data = my_attendance(conn, student.student_id)
        _print_attendance(data)
        print("\n  1. Self-certify an absence    0. Back")
        if input("\n  Choice: ").strip() != "1":
            return
        try:
            start = date.fromisoformat(input("  First day absent (YYYY-MM-DD): ").strip())
            end_raw = input("  Last day absent (YYYY-MM-DD, Enter = same day): ").strip()
            end = date.fromisoformat(end_raw) if end_raw else start
            reason = input("  Reason: ").strip()
            with transaction() as conn:
                certify_own_absence(conn, student.student_id, start, end, reason)
            print("\n  Absence self-certified.")
        except Exception as exc:
            print(f"\n  Not recorded: {exc}")
        _pause()


def _print_attendance(data: dict) -> None:
    s = data["summary"]
    start, end = data["window"]
    _header(f"MY ATTENDANCE  ({start} to {end})")
    pct = f"{s['attendance_pct']}%" if s.get("attendance_pct") is not None else "—"
    cover = f"{s['coverage_pct']}%" if s.get("coverage_pct") is not None else "—"
    print(f"  Attendance rate: {pct}   Sessions expected: {s['expected']}   "
          f"Registers taken: {cover}   Missed in a row: {s['consecutive_missed']}")
    print("  (Present + late over sessions with a register; excused absences count neither way.)")
    if data.get("ukvi"):
        u = data["ukvi"]
        print(f"\n  Student route visa: {u['consecutive_missed']} contact points missed in a row; "
              f"{u['limit']} in a row must be reported to UKVI. Last attended: "
              f"{u['last_engaged'] or '—'}.")
    print("\n  BY MODULE")
    _table(data["modules"], [("module_code", "Module", 12), ("expected", "Exp", 6),
                             ("present", "Pres", 6), ("late", "Late", 6), ("excused", "Exc", 6),
                             ("absent", "Abs", 6), ("no_register", "NoReg", 7),
                             ("attendance_pct", "Rate%", 7)],
           "No timetabled sessions in this period.")
    print("\n  LATEST SESSIONS")
    _table(list(reversed(data["sessions"]))[:15],
           [("date", "Date", 12), ("module_code", "Module", 12), ("start_time", "Start", 8),
            ("outcome", "Outcome", 14)], "No sessions.")
    print("\n  SELF-CERTIFICATIONS THIS YEAR")
    _table(data["self_certifications"], [("date", "From", 12), ("date_end", "To", 12),
                                         ("reason", "Reason", 40)], "None.")


# ----------------------------------------------------------------------
# My Mitigating Circumstances
# ----------------------------------------------------------------------

def run_my_mitigating_circumstances(auth) -> None:
    from education_system.systems.university.application.self_service import (
        mitigating_circumstances as mc,
    )
    from education_system.systems.university.domains.assessment.domain.mitigating_circumstances.services.mitigating_circumstances_service import (
        VALID_GROUNDS,
        MitigatingCircumstancesService,
    )
    student = _student(auth)
    if student is None:
        return
    service = MitigatingCircumstancesService()
    actions = {
        "1": lambda: _mc_list(service, student, mc),
        "2": lambda: _mc_submit(service, student, mc, VALID_GROUNDS),
        "3": lambda: _mc_evidence(service, student, mc),
        "4": lambda: mc.withdraw_own_claim(service, student.student_id,
                                           int(input("  Claim # to withdraw: ").strip())),
        "5": lambda: _table(mc.own_extensions(service, student.student_id),
                            [("module_code", "Module", 12), ("assessment_ref", "Assessment", 20),
                             ("new_deadline", "New deadline", 14), ("extension_days", "Days", 6)],
                            "No extensions granted."),
    }
    while True:
        _header("MY MITIGATING CIRCUMSTANCES")
        print("  1. My claims\n  2. Submit a claim\n  3. Add evidence to a claim\n"
              "  4. Withdraw a claim\n  5. Extensions granted\n  0. Back")
        choice = input("\n  Choice: ").strip()
        if choice not in actions:
            return
        try:
            actions[choice]()
        except Exception as exc:
            print(f"\n  {exc}")
        _pause()


def _mc_list(service, student, mc) -> None:
    claims = mc.own_claims(service, student.student_id)
    _table(claims, [("id", "#", 6), ("module_code", "Module", 12),
                    ("assessment_ref", "Assessment", 20), ("grounds", "Grounds", 14),
                    ("status", "Status", 18), ("submitted_at", "Submitted", 20)],
           "You have no claims.")


def _mc_submit(service, student, mc, grounds) -> None:
    print(f"  Grounds: {', '.join(grounds)}")
    data = {
        "module_code": input("  Module code: "),
        "assessment_ref": input("  Assessment (e.g. Coursework 1): "),
        "grounds": input("  Grounds: ").strip().lower(),
        "period_start": input("  Affected from (YYYY-MM-DD): "),
        "period_end": input("  Affected until (YYYY-MM-DD): "),
        "description": input("  What happened: "),
        "impact_statement": input("  How it affected your assessment: "),
        "requested_remedy": input("  What you are asking for: "),
    }
    claim_id = mc.submit_own_claim(service, student.student_id, student.username, data, grounds)
    print(f"\n  Claim #{claim_id} submitted. Add your evidence to it next.")


def _mc_evidence(service, student, mc) -> None:
    claim_id = int(input("  Claim #: ").strip())
    print(f"  Types: {', '.join(mc.EVIDENCE_TYPES)}")
    mc.add_own_evidence(service, student.student_id, claim_id,
                        input("  Type: ").strip(), input("  What it is: "),
                        input("  Reference (optional): "))
    print("\n  Evidence added; the claim is now under review.")


# ----------------------------------------------------------------------
# My Parking / My Placement
# ----------------------------------------------------------------------

def run_my_parking(auth) -> None:
    from education_system.systems.university.application.self_service.parking import my_parking
    from education_system.systems.university.infrastructure.database.db import get_connection
    student = _student(auth)
    if student is None:
        return
    with closing(get_connection()) as conn:
        data = my_parking(conn, student)
    _header("MY PARKING")
    print("\n  PERMITS")
    _table(data["permits"], [("permit_number", "Permit", 14), ("zone", "Zone", 10),
                             ("start_date", "From", 12), ("end_date", "To", 12),
                             ("active_status", "Status", 10)], "No permits on record.")
    print("\n  VEHICLES")
    _table(data["vehicles"], [("license_plate", "Registration", 14), ("make", "Make", 14),
                              ("model", "Model", 14), ("color", "Colour", 10)],
           "No vehicles registered.")
    print("\n  FINES")
    _table(data["violations"], [("violation_date", "Date", 12), ("violation_type", "Offence", 22),
                                ("fine_amount", "Fine £", 8), ("payment_status", "Payment", 10)],
           "No parking fines.")
    print(f"\n  Unpaid fines: £{data['outstanding']:.2f}")
    print("  To apply for a permit, register a vehicle or pay/appeal a fine, contact the "
          "Parking office.")
    _pause()


def run_my_placement(auth) -> None:
    from education_system.systems.university.application.self_service.placements import (
        my_placement,
    )
    from education_system.systems.university.infrastructure.database.db import get_connection
    student = _student(auth)
    if student is None:
        return
    with closing(get_connection()) as conn:
        data = my_placement(conn, student.student_id)
    _header("MY PLACEMENT")
    p = data["profile"]
    if not p:
        print("  You are not enrolled on a placement.")
    else:
        print(f"  Employer: {p.get('employer') or '—'}   Supervisor: {p.get('supervisor') or '—'}")
        print(f"  Dates: {p.get('start_date') or '—'} to {p.get('end_date') or '—'}")
    print(f"  Hours logged: {data['total']:g}   Signed off: {data['signed_off']:g} of "
          f"{data['required']}   Still needed: {data['remaining']:g}")
    _table(data["hours"], [("log_date", "Date", 12), ("hours", "Hours", 7),
                           ("activity", "Activity", 30), ("signed_off", "Signed", 7)],
           "No hours logged yet.")
    print("\n  Hours are logged and signed off by your supervisor and the placement office.")
    _pause()
