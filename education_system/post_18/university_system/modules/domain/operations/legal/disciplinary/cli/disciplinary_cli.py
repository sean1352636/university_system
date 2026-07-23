"""
Disciplinary Portal — interactive CLI.

Wired to ``DatabaseManager`` in ``disciplinary.disciplinary_portal``, which
reads/writes the central ``student_records.db`` — the same database the
Disciplinary Actions Portal GUI (``disciplinary_portal.py``) uses. Anything
created here is visible in the GUI and vice-versa.

Covers: Disciplinary Cases/Incidents (list/create/view/update status),
Disciplinary Actions (list/add), Academic Misconduct (list/escalate), a
read-only Student lookup helper, and Statistics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from education_system.post_18.university_system.modules.domain.operations.legal.disciplinary.disciplinary_portal import (  # noqa: E501
    DatabaseManager,
)


# --------------------------------------------------------------------------- #
# Input helpers
# --------------------------------------------------------------------------- #
def _prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def _prompt_int(text: str, *, allow_blank: bool = True) -> Optional[int]:
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("A value is required.")
            continue
        try:
            return int(raw)
        except ValueError:
            print("Please enter a whole number.")


def _pause() -> None:
    input("\nPress Enter to continue...")


def _header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _current_username(auth) -> str:
    try:
        user = getattr(auth, "current_user", None)
        if isinstance(user, dict):
            return user.get("username") or user.get("name") or "cli-user"
    except Exception:
        pass
    return "cli-user"


# Reference vocabularies (mirror the GUI's DisciplinaryPortal constants).
_INCIDENT_TYPES = (
    "Academic Misconduct, Plagiarism, Cheating, Disruptive Behavior, "
    "Harassment, Property Damage, Substance Abuse, Violence, "
    "Attendance Violation, Code of Conduct Violation, Other")
_SEVERITY_LEVELS = "Minor / Major / Critical"
_ACTION_TYPES = (
    "Verbal Warning, Written Warning, Probation, Community Service, Fine, "
    "Suspension, Expulsion, Mandatory Counseling, Course Failure, "
    "Educational Sanction, No Action")
_STATUS_OPTIONS = "Open / Under Review / Resolved / Appealed / Closed"


def _db() -> DatabaseManager:
    return DatabaseManager()


# --------------------------------------------------------------------------- #
# 1. Incidents / Cases
# --------------------------------------------------------------------------- #
def _list_incidents() -> None:
    incidents = _db().get_all_incidents()
    if not incidents:
        print("\nNo disciplinary incidents recorded yet.")
        return
    # (record_id, user_id, student_name, date, type, severity, status)
    print(f"\n{'ID':<5}{'Student':<12}{'Name':<22}{'Date':<12}"
          f"{'Type':<22}{'Severity':<10}Status")
    print("-" * 92)
    for r in incidents:
        print(f"{r[0]:<5}{(str(r[1]) or '')[:11]:<12}"
              f"{(r[2] or '')[:21]:<22}{(r[3] or '')[:11]:<12}"
              f"{(r[4] or '')[:21]:<22}{(r[5] or '')[:9]:<10}"
              f"{r[6] or 'Open'}")


def _create_incident(auth) -> None:
    print(f"\nIncident types: {_INCIDENT_TYPES}")
    print(f"Severity levels: {_SEVERITY_LEVELS}")
    student_id = _prompt("Student id")
    if not student_id:
        print("Student id is required.")
        return
    if not _db().get_student(student_id):
        print(f"\n✗ No student with id '{student_id}' (see Students menu).")
        return
    itype = _prompt("Incident type", default="Other")
    severity = _prompt("Severity (Minor/Major/Critical)", default="Minor")
    idate = _prompt("Incident date (YYYY-MM-DD)",
                    default=datetime.now().strftime("%Y-%m-%d"))
    description = _prompt("Description (optional)")
    location = _prompt("Location (optional)")
    status = _prompt("Status", default="Open")
    reporter = _current_username(auth)
    try:
        rid = _db().add_incident(
            (student_id, idate, itype, severity, description,
             reporter, location, status, None))
        print(f"\n✓ Created incident {rid} for student {student_id} "
              f"(reported by {reporter}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _view_incident() -> None:
    iid = _prompt_int("Incident id", allow_blank=False)
    db = _db()
    incident = db.get_incident(iid)
    if not incident:
        print(f"\nNo incident with id {iid}.")
        return
    # (id, student_id, date, type, severity, description, reported_by,
    #  location, status)
    student = db.get_student(incident[1])
    name = f"{student[1]} {student[2]}" if student else "Unknown"
    print(f"\n--- Incident {iid} ---")
    print(f"  Student      : {name} ({incident[1]})")
    print(f"  Date         : {incident[2] or '-'}")
    print(f"  Type         : {incident[3] or '-'}")
    print(f"  Severity     : {incident[4] or '-'}")
    print(f"  Location     : {incident[7] or '-'}")
    print(f"  Reported by  : {incident[6] or '-'}")
    print(f"  Status       : {incident[8] or 'Open'}")
    print(f"  Description  : {incident[5] or '-'}")
    actions = db.get_actions_by_incident(iid)
    print(f"\n  Actions ({len(actions)}):")
    for a in actions:
        # (action_id, record_id, action_type, effective_date,
        #  conditions, imposed_by, reason)
        print(f"    #{a[0]} {a[2]} [{a[3] or '-'}] by {a[5] or '-'}"
              f" — {(a[6] or '')[:50]}")
    case_id = db.find_misconduct_case_for_record(iid)
    if case_id:
        print(f"\n  Linked misconduct case: {case_id}")


def _update_incident_status() -> None:
    iid = _prompt_int("Incident id", allow_blank=False)
    if not _db().get_incident(iid):
        print(f"\nNo incident with id {iid}.")
        return
    status = _prompt(f"New status ({_STATUS_OPTIONS})")
    if not status:
        print("Status is required.")
        return
    try:
        _db().update_incident_status(iid, status)
        print(f"\n✓ Updated incident {iid} → {status}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _incidents_menu(auth) -> None:
    while True:
        _header("Disciplinary Incidents")
        print("[1] List incidents")
        print("[2] Create incident")
        print("[3] View incident (+ actions)")
        print("[4] Update incident status")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_incidents()
        elif choice == "2":
            _create_incident(auth)
        elif choice == "3":
            _view_incident()
        elif choice == "4":
            _update_incident_status()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 2. Disciplinary Actions
# --------------------------------------------------------------------------- #
def _list_actions() -> None:
    iid = _prompt_int("Incident id", allow_blank=False)
    actions = _db().get_actions_by_incident(iid)
    if not actions:
        print(f"\nNo actions recorded for incident {iid}.")
        return
    print(f"\n{'ID':<5}{'Type':<22}{'Date':<12}{'Issued by':<16}Notes")
    print("-" * 78)
    for a in actions:
        print(f"{a[0]:<5}{(a[2] or '')[:21]:<22}{(a[3] or '')[:11]:<12}"
              f"{(a[5] or '')[:15]:<16}{(a[6] or '')[:25]}")


def _add_action(auth) -> None:
    iid = _prompt_int("Incident id", allow_blank=False)
    if not _db().get_incident(iid):
        print(f"\nNo incident with id {iid}.")
        return
    print(f"\nAction types: {_ACTION_TYPES}")
    action_type = _prompt("Action type", default="Written Warning")
    action_date = _prompt("Effective date (YYYY-MM-DD)",
                          default=datetime.now().strftime("%Y-%m-%d"))
    duration = _prompt("Duration / conditions "
                       "(e.g. days for suspension, amount for fine)")
    notes = _prompt("Notes / reason (optional)")
    issued_by = _current_username(auth)
    try:
        _db().add_action(
            (iid, action_type, action_date, duration, issued_by, notes))
        print(f"\n✓ Added '{action_type}' action to incident {iid} "
              f"(by {issued_by}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _actions_menu(auth) -> None:
    while True:
        _header("Disciplinary Actions")
        print("[1] List actions for an incident")
        print("[2] Add action to an incident")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_actions()
        elif choice == "2":
            _add_action(auth)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 3. Academic Misconduct
# --------------------------------------------------------------------------- #
def _list_misconduct() -> None:
    cases = _db().list_misconduct_cases()
    if not cases:
        print("\nNo academic misconduct cases recorded yet.")
        return
    # (case_id, student_name, student_id, violation_type, status,
    #  severity, date_filed, source_record_id)
    print(f"\n{'Case ID':<24}{'Student':<20}{'Violation':<20}"
          f"{'Status':<16}{'Severity':<10}From#")
    print("-" * 96)
    for c in cases:
        print(f"{(c[0] or '')[:23]:<24}{(c[1] or '')[:19]:<20}"
              f"{(c[3] or '')[:19]:<20}{(c[4] or '')[:15]:<16}"
              f"{(c[5] or '')[:9]:<10}{c[7] or '-'}")


def _escalate_incident(auth) -> None:
    iid = _prompt_int("Incident id to escalate", allow_blank=False)
    db = _db()
    if not db.get_incident(iid):
        print(f"\nNo incident with id {iid}.")
        return
    existing = db.find_misconduct_case_for_record(iid)
    if existing:
        print(f"\nIncident {iid} is already linked to case {existing}.")
        return
    try:
        case_id = db.escalate_to_misconduct(iid, imposed_by=_current_username(auth))
        print(f"\n✓ Escalated incident {iid} → misconduct case {case_id} "
              "(incident marked 'Escalated').")
    except Exception as e:
        print(f"\n✗ {e}")


def _misconduct_menu(auth) -> None:
    while True:
        _header("Academic Misconduct")
        print("[1] List misconduct cases")
        print("[2] Escalate an incident to a misconduct case")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_misconduct()
        elif choice == "2":
            _escalate_incident(auth)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 4. Students (read-only lookup helper)
# --------------------------------------------------------------------------- #
def _list_students() -> None:
    query = _prompt("Search id/name/course (blank = list all)")
    db = _db()
    students = db.search_students(query) if query else db.get_all_students()
    if not students:
        print("\nNo students found.")
        return
    # (student_id, first, last, email, department, year, enrollment)
    print(f"\n{'ID':<12}{'Name':<26}{'Email':<28}Department")
    print("-" * 80)
    for s in students[:100]:
        name = f"{s[1] or ''} {s[2] or ''}".strip()
        print(f"{(str(s[0]) or '')[:11]:<12}{name[:25]:<26}"
              f"{(s[3] or '')[:27]:<28}{s[4] or '-'}")


def _students_menu(auth) -> None:
    while True:
        _header("Students (read-only)")
        print("[1] List / search students")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_students()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 5. Statistics
# --------------------------------------------------------------------------- #
def _show_statistics() -> None:
    stats = _db().get_statistics()
    print("\n--- Disciplinary Statistics ---")
    print(f"  Total students   : {stats.get('total_students', 0)}")
    print(f"  Total incidents  : {stats.get('total_incidents', 0)}")
    print(f"  Open incidents   : {stats.get('open_incidents', 0)}")
    print(f"  Resolved         : {stats.get('resolved_incidents', 0)}")
    print(f"  Total actions    : {stats.get('total_actions', 0)}")
    by_sev = stats.get('by_severity') or {}
    if by_sev:
        print("\n  By severity:")
        for sev, count in by_sev.items():
            print(f"    {(sev or 'Unknown'):<12}: {count}")
    top = stats.get('top_types') or []
    if top:
        print("\n  Top incident types:")
        for itype, count in top:
            print(f"    {(itype or 'Unknown'):<26}: {count}")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_disciplinary_menu(auth) -> None:
    """Run the Disciplinary Portal CLI loop."""
    while True:
        print("\n" + "=" * 50)
        print("    DISCIPLINARY ACTIONS PORTAL")
        print("=" * 50)
        print("1. Disciplinary Incidents")
        print("2. Disciplinary Actions")
        print("3. Academic Misconduct")
        print("4. Students (lookup)")
        print("5. Statistics")
        print("6. Return to Main Menu")
        print("=" * 50)

        try:
            choice = input("\nEnter your choice (1-6): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        try:
            if choice == "1":
                _incidents_menu(auth)
            elif choice == "2":
                _actions_menu(auth)
            elif choice == "3":
                _misconduct_menu(auth)
            elif choice == "4":
                _students_menu(auth)
            elif choice == "5":
                _show_statistics()
                _pause()
            elif choice == "6":
                print("Returning to main menu...")
                return
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:  # keep the menu resilient
            print(f"❌ Error: {e}")
