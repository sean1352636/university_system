"""
T-Level / Industry Placement Hours Tracker — interactive CLI.

Wired to the ``Database`` and helper functions in
``placements.placement_service``, which read/write the shared
``student_records.db`` — the same database the Placement Tracker GUI
(``placement_tracker.py``) uses. Anything created here is visible in the
GUI and vice-versa.

Covers: Students (add/edit/delete/list), placement hours
(log/edit/delete), export summary, and "Submit as APL evidence".
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from typing import Optional

from education_system.systems.university.domain.progression.placements.placement_service import (
    REQUIRED_HOURS,
    Database,
    export_summary_rows,
    submit_as_apl_evidence,
)


# --------------------------------------------------------------------------- #
# Input helpers
# --------------------------------------------------------------------------- #
def _prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def _prompt_float(text: str, *, allow_blank: bool = True) -> Optional[float]:
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("A value is required.")
            continue
        try:
            return float(raw)
        except ValueError:
            print("Please enter a number.")


def _prompt_bool(text: str, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    raw = input(f"{text} ({d}): ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "true", "1")


def _prompt_date(text: str, *, allow_blank: bool = True, default: str = "") -> Optional[str]:
    while True:
        raw = _prompt(text, default=default)
        if not raw:
            if allow_blank:
                return None
            print("A date is required.")
            continue
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            return raw
        except ValueError:
            print("Please use YYYY-MM-DD format.")


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


# --------------------------------------------------------------------------- #
# 1. Students
# --------------------------------------------------------------------------- #
def _list_students(db: Database) -> None:
    search = _prompt("Search id/name/course/employer (optional)")
    students = db.get_all_students(search)
    if not students:
        print("\nNo students enrolled in placements yet.")
        return
    print(f"\n{'Student ID':<14}{'Name':<26}{'Course':<22}{'Cohort':<12}Employer")
    print("-" * 86)
    for s in students:
        _pk, sid, fn, ln, course, cohort, employer = s
        print(f"{(sid or '')[:13]:<14}{(f'{ln}, {fn}')[:25]:<26}"
              f"{(course or '')[:21]:<22}{(cohort or '-')[:11]:<12}"
              f"{employer or '-'}")


def _student_data_from_prompts(default_sid: str = "") -> Optional[tuple]:
    student_id = _prompt("Student ID", default=default_sid)
    first = _prompt("First name")
    last = _prompt("Last name")
    course = _prompt("Course")
    if not all([student_id, first, last, course]):
        print("Student ID, first name, last name and course are required.")
        return None
    cohort = _prompt("Cohort (optional)")
    email = _prompt("Email (optional)")
    employer = _prompt("Employer (optional)")
    supervisor = _prompt("Supervisor (optional)")
    start = _prompt_date("Start date (YYYY-MM-DD, optional)")
    end = _prompt_date("End date (YYYY-MM-DD, optional)")
    return (student_id, first, last, course, cohort or None, email or None,
            employer or None, supervisor or None, start, end)


def _add_student(db: Database) -> None:
    data = _student_data_from_prompts()
    if not data:
        return
    try:
        sid = db.add_student(data)
        print(f"\n✓ Enrolled student '{data[1]} {data[2]}' (id={sid}) in placements.")
    except Exception as e:
        print(f"\n✗ {e}")


def _edit_student(db: Database) -> None:
    old_id = _prompt("Student ID to edit")
    if not old_id:
        print("Student ID is required.")
        return
    existing = db.get_student(old_id)
    if not existing:
        print(f"\nNo student with id {old_id}.")
        return
    print("(Enter new values; Student ID defaults to the current one.)")
    data = _student_data_from_prompts(default_sid=old_id)
    if not data:
        return
    try:
        db.update_student(old_id, data)
        print(f"\n✓ Updated placement student {old_id}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _delete_student(db: Database) -> None:
    sid = _prompt("Student ID to remove from placements")
    if not sid:
        print("Student ID is required.")
        return
    if not _prompt_bool("Remove placement enrollment and all hours logs? "
                        "(central student record is kept)", default=False):
        print("Cancelled.")
        return
    try:
        db.delete_student(sid)
        print(f"\n✓ Removed placement enrollment for {sid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _students_menu(db: Database, auth) -> None:
    while True:
        _header("Placement Students")
        print("[1] List students")
        print("[2] Add student")
        print("[3] Edit student")
        print("[4] Delete student (remove from placements)")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_students(db)
        elif choice == "2":
            _add_student(db)
        elif choice == "3":
            _edit_student(db)
        elif choice == "4":
            _delete_student(db)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 2. Hours log
# --------------------------------------------------------------------------- #
def _show_progress(db: Database, student_pk: str) -> None:
    total = db.get_total_hours(student_pk)
    signed = db.get_signed_off_hours(student_pk)
    remaining = max(0, REQUIRED_HOURS - signed)
    pct = (signed / REQUIRED_HOURS * 100) if REQUIRED_HOURS else 0
    print(f"\nLogged: {total:.1f} h   Signed off: {signed:.1f} h   "
          f"Remaining: {remaining:.1f} h   ({pct:.1f}% of {REQUIRED_HOURS} h)")
    if signed >= REQUIRED_HOURS:
        print("✓ Requirement met!")


def _list_hours(db: Database) -> None:
    sid = _prompt("Student ID")
    if not sid:
        print("Student ID is required.")
        return
    if not db.get_student(sid):
        print(f"\nNo student with id {sid}.")
        return
    logs = db.get_hours_for_student(sid)
    if not logs:
        print("\nNo hours logged for this student.")
    else:
        print(f"\n{'Log ID':<8}{'Date':<12}{'Hours':<8}{'Signed':<8}Activity")
        print("-" * 62)
        for log in logs:
            log_pk, log_date, hours, activity, signoff, _notes = log
            print(f"{log_pk:<8}{(log_date or '')[:11]:<12}{hours:<8.1f}"
                  f"{'✓' if signoff else '✗':<8}{(activity or '-')[:30]}")
    _show_progress(db, sid)


def _log_hours(db: Database) -> None:
    sid = _prompt("Student ID")
    if not sid:
        print("Student ID is required.")
        return
    if not db.get_student(sid):
        print(f"\nNo student with id {sid}.")
        return
    log_date = _prompt_date("Date (YYYY-MM-DD)", allow_blank=False,
                            default=date.today().isoformat())
    hours = _prompt_float("Hours", allow_blank=False)
    if hours is None or hours <= 0 or hours > 24:
        print("Hours must be a number between 0 and 24.")
        return
    activity = _prompt("Activity (optional)")
    signoff = 1 if _prompt_bool("Signed off by supervisor?", default=False) else 0
    notes = _prompt("Notes (optional)")
    try:
        db.add_hours(sid, log_date, hours, activity or None, signoff, notes or None)
        print(f"\n✓ Logged {hours:.1f} h for student {sid} on {log_date}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _edit_hours(db: Database) -> None:
    sid = _prompt("Student ID")
    if not sid:
        print("Student ID is required.")
        return
    logs = db.get_hours_for_student(sid)
    if not logs:
        print("\nNo hours logged for this student.")
        return
    print(f"\n{'Log ID':<8}{'Date':<12}{'Hours':<8}Activity")
    print("-" * 44)
    for log in logs:
        print(f"{log[0]:<8}{(log[1] or '')[:11]:<12}{log[2]:<8.1f}{(log[3] or '-')[:24]}")
    log_pk = _prompt("Log ID to edit")
    existing = next((log for log in logs if str(log[0]) == log_pk), None)
    if not existing:
        print("No matching log entry.")
        return
    log_date = _prompt_date("Date (YYYY-MM-DD)", allow_blank=False,
                            default=existing[1] or date.today().isoformat())
    hours = _prompt_float(f"Hours [{existing[2]}]")
    if hours is None:
        hours = existing[2]
    if hours <= 0 or hours > 24:
        print("Hours must be between 0 and 24.")
        return
    activity = _prompt("Activity", default=existing[3] or "")
    signoff = 1 if _prompt_bool("Signed off by supervisor?",
                                default=bool(existing[4])) else 0
    notes = _prompt("Notes", default=existing[5] or "")
    try:
        db.update_hours(int(log_pk), log_date, hours, activity or None, signoff,
                        notes or None)
        print(f"\n✓ Updated log entry {log_pk}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _delete_hours(db: Database) -> None:
    log_pk = _prompt("Log ID to delete")
    if not log_pk.isdigit():
        print("Please enter a numeric Log ID.")
        return
    if not _prompt_bool("Delete this hours log entry?", default=False):
        print("Cancelled.")
        return
    try:
        db.delete_hours(int(log_pk))
        print(f"\n✓ Deleted log entry {log_pk}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _hours_menu(db: Database, auth) -> None:
    while True:
        _header("Placement Hours")
        print("[1] View hours for a student")
        print("[2] Log hours")
        print("[3] Edit an hours entry")
        print("[4] Delete an hours entry")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_hours(db)
        elif choice == "2":
            _log_hours(db)
        elif choice == "3":
            _edit_hours(db)
        elif choice == "4":
            _delete_hours(db)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 3. Export summary
# --------------------------------------------------------------------------- #
def _export_summary(db: Database) -> None:
    rows = export_summary_rows(db)
    if len(rows) <= 1:
        print("\nNo placement students to summarise.")
        return
    header, *data = rows
    # On-screen summary
    print(f"\n{'Student ID':<14}{'Name':<24}{'Total':<9}{'Signed':<9}% Complete")
    print("-" * 66)
    for r in data:
        print(f"{str(r[0])[:13]:<14}{str(r[1])[:23]:<24}{str(r[5]):<9}"
              f"{str(r[6]):<9}{r[9]}")
    # Optional CSV export
    if _prompt_bool("\nExport to CSV file?", default=False):
        default_path = f"placement_hours_{date.today().isoformat()}.csv"
        path = _prompt("Output path", default=default_path)
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(data)
            print(f"\n✓ Exported {len(data)} row(s) to {path}.")
        except Exception as e:
            print(f"\n✗ {e}")


# --------------------------------------------------------------------------- #
# 4. APL evidence
# --------------------------------------------------------------------------- #
def _submit_apl(db: Database) -> None:
    sid = _prompt("Student ID")
    if not sid:
        print("Student ID is required.")
        return
    try:
        cid = submit_as_apl_evidence(db, sid)
        print(f"\n✓ Placement summary added to APL claim #{cid} for student {sid}.")
    except Exception as e:
        print(f"\n✗ {e}")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_placements_menu(auth) -> None:
    """Run the Placement Hours Tracker CLI loop."""
    try:
        db = Database()
    except Exception as e:
        print(f"❌ Could not open the placement database: {e}")
        return
    try:
        while True:
            print("\n" + "=" * 50)
            print("    PLACEMENT HOURS TRACKER")
            print(f"    (T-Level requirement: {REQUIRED_HOURS} hours)")
            print("=" * 50)
            print("1. Students")
            print("2. Placement Hours")
            print("3. Export Summary")
            print("4. Submit as APL evidence")
            print("5. Return to Main Menu")
            print("=" * 50)

            try:
                choice = input("\nEnter your choice (1-5): ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                return

            try:
                if choice == "1":
                    _students_menu(db, auth)
                elif choice == "2":
                    _hours_menu(db, auth)
                elif choice == "3":
                    _export_summary(db)
                    _pause()
                elif choice == "4":
                    _submit_apl(db)
                    _pause()
                elif choice == "5":
                    print("Returning to main menu...")
                    return
                else:
                    print("❌ Invalid choice.")
            except KeyboardInterrupt:
                print("\nCancelled.")
            except Exception as e:  # keep the menu resilient
                print(f"❌ Error: {e}")
    finally:
        db.close()
