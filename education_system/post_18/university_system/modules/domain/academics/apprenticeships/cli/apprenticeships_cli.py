"""
University Apprenticeship Management — interactive CLI.

Wired to ``ApprenticeshipService`` in
``apprenticeships.apprenticeship_service``, which reads/writes the shared
``student_records.db`` — the same database the Apprenticeship GUI
(``apprenticeship_system.py``) uses. Anything created here is visible in
the GUI and vice-versa.

Covers: Students, Employers, Apprenticeship listings, and Applications
(submit / update status), plus "Submit as APL evidence" for a student.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from education_system.post_18.university_system.modules.domain.academics.apprenticeships.apprenticeship_service import (
    ApprenticeshipService,
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
def _list_students(svc: ApprenticeshipService) -> None:
    search = _prompt("Search name/id/course (optional)")
    students = svc.list_students(search=search)
    if not students:
        print("\nNo students found.")
        return
    print(f"\n{'Student ID':<14}{'Name':<28}{'Course':<22}{'Yr':<5}GPA")
    print("-" * 74)
    for s in students:
        name = f"{s.get('first_name') or ''} {s.get('last_name') or ''}".strip()
        gpa = s.get("gpa")
        print(f"{(s.get('student_id') or '')[:13]:<14}{name[:27]:<28}"
              f"{(s.get('course') or '')[:21]:<22}"
              f"{s.get('year_of_study') if s.get('year_of_study') is not None else '-':<5}"
              f"{gpa if gpa is not None else '-'}")


def _add_student(svc: ApprenticeshipService) -> None:
    student_id = _prompt("Student ID")
    first = _prompt("First name")
    last = _prompt("Last name")
    email = _prompt("Email")
    course = _prompt("Course")
    if not all([student_id, first, last, email, course]):
        print("Student ID, name, email and course are required.")
        return
    year = _prompt_int("Year of study (optional)") or 0
    gpa = _prompt_float("GPA (optional)")
    try:
        sid = svc.add_student(student_id, first, last, email, course, year, gpa)
        print(f"\n✓ Added student '{first} {last}' (id={sid}).")
    except sqlite3.IntegrityError:
        print("\n✗ A student with this Student ID already exists.")
    except Exception as e:
        print(f"\n✗ {e}")


def _update_student(svc: ApprenticeshipService) -> None:
    old_id = _prompt("Existing Student ID to update", )
    if not old_id:
        print("Student ID is required.")
        return
    student_id = _prompt("New Student ID", default=old_id)
    first = _prompt("First name")
    last = _prompt("Last name")
    email = _prompt("Email")
    course = _prompt("Course")
    if not all([student_id, first, last, email, course]):
        print("All fields except year/GPA are required.")
        return
    year = _prompt_int("Year of study (optional)") or 0
    gpa = _prompt_float("GPA (optional)")
    try:
        svc.update_student(old_id, student_id, first, last, email, course, year, gpa)
        print(f"\n✓ Updated student {old_id}. (Note: their applications were cleared.)")
    except Exception as e:
        print(f"\n✗ {e}")


def _delete_student(svc: ApprenticeshipService) -> None:
    sid = _prompt("Student ID to delete")
    if not sid:
        print("Student ID is required.")
        return
    if _prompt("Delete this student and all their applications? (y/N)").lower() not in ("y", "yes"):
        print("Cancelled.")
        return
    try:
        svc.delete_student(sid)
        print(f"\n✓ Deleted student {sid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _submit_student_apl(svc: ApprenticeshipService) -> None:
    sid = _prompt("Student ID")
    if not sid:
        print("Student ID is required.")
        return
    course = _prompt("Target course (optional)")
    try:
        cid = svc.submit_as_apl(sid, course or None)
        print(f"\n✓ Added apprenticeship evidence to APL claim #{cid} for student {sid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _students_menu(svc: ApprenticeshipService, auth) -> None:
    while True:
        _header("Students")
        print("[1] List students")
        print("[2] Add student")
        print("[3] Update student")
        print("[4] Delete student")
        print("[5] Submit as APL evidence")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_students(svc)
        elif choice == "2":
            _add_student(svc)
        elif choice == "3":
            _update_student(svc)
        elif choice == "4":
            _delete_student(svc)
        elif choice == "5":
            _submit_student_apl(svc)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 2. Employers
# --------------------------------------------------------------------------- #
def _list_employers(svc: ApprenticeshipService) -> None:
    employers = svc.list_employers()
    if not employers:
        print("\nNo employers found.")
        return
    print(f"\n{'ID':<5}{'Company':<26}{'Contact':<20}{'Industry':<16}Email")
    print("-" * 82)
    for e in employers:
        print(f"{e['employer_id']:<5}{(e.get('company_name') or '')[:25]:<26}"
              f"{(e.get('contact_person') or '')[:19]:<20}"
              f"{(e.get('industry') or '')[:15]:<16}"
              f"{e.get('contact_email') or '-'}")


def _add_employer(svc: ApprenticeshipService) -> None:
    company = _prompt("Company name")
    contact = _prompt("Contact person")
    email = _prompt("Email")
    if not all([company, contact, email]):
        print("Company name, contact and email are required.")
        return
    phone = _prompt("Phone (optional)")
    industry = _prompt("Industry (optional)")
    address = _prompt("Address (optional)")
    try:
        eid = svc.add_employer(company, contact, email, phone, industry, address)
        print(f"\n✓ Added employer '{company}' (id={eid}).")
    except sqlite3.IntegrityError:
        print("\n✗ An employer with this company name already exists.")
    except Exception as e:
        print(f"\n✗ {e}")


def _update_employer(svc: ApprenticeshipService) -> None:
    eid = _prompt_int("Employer id", allow_blank=False)
    company = _prompt("Company name")
    contact = _prompt("Contact person")
    email = _prompt("Email")
    if not all([company, contact, email]):
        print("Company name, contact and email are required.")
        return
    phone = _prompt("Phone (optional)")
    industry = _prompt("Industry (optional)")
    address = _prompt("Address (optional)")
    try:
        svc.update_employer(eid, company, contact, email, phone, industry, address)
        print(f"\n✓ Updated employer {eid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _delete_employer(svc: ApprenticeshipService) -> None:
    eid = _prompt_int("Employer id", allow_blank=False)
    if _prompt("Delete this employer AND its apprenticeships/applications? (y/N)").lower() not in ("y", "yes"):
        print("Cancelled.")
        return
    try:
        svc.delete_employer(eid)
        print(f"\n✓ Deleted employer {eid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _employers_menu(svc: ApprenticeshipService, auth) -> None:
    while True:
        _header("Employers")
        print("[1] List employers")
        print("[2] Add employer")
        print("[3] Update employer")
        print("[4] Delete employer")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_employers(svc)
        elif choice == "2":
            _add_employer(svc)
        elif choice == "3":
            _update_employer(svc)
        elif choice == "4":
            _delete_employer(svc)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 3. Apprenticeships
# --------------------------------------------------------------------------- #
def _list_apprenticeships(svc: ApprenticeshipService) -> None:
    status = _prompt("Status filter (Open/Closed/Filled, blank = all)")
    apps = svc.list_apprenticeships(status=status or None)
    if not apps:
        print("\nNo apprenticeships found.")
        return
    print(f"\n{'ID':<5}{'Title':<26}{'Company':<22}{'Months':<8}{'Salary':<10}Status")
    print("-" * 82)
    for a in apps:
        salary = a.get("salary")
        salary_str = f"£{salary:.0f}" if salary else "-"
        print(f"{a['id']:<5}{(a.get('title') or '')[:25]:<26}"
              f"{(a.get('company_name') or '')[:21]:<22}"
              f"{a.get('duration_months') if a.get('duration_months') is not None else '-':<8}"
              f"{salary_str:<10}{a.get('status') or ''}")


def _add_apprenticeship(svc: ApprenticeshipService) -> None:
    _list_employers(svc)
    title = _prompt("Title")
    employer_id = _prompt_int("Employer id (see list above)", allow_blank=False)
    duration = _prompt_int("Duration (months)", allow_blank=False)
    if not title or not duration:
        print("Title and duration are required.")
        return
    description = _prompt("Description (optional)")
    salary = _prompt_float("Salary (optional)")
    location = _prompt("Location (optional)")
    course = _prompt("Required course (optional)")
    min_year = _prompt_int("Min year (optional)") or 1
    positions = _prompt_int("Positions available (optional)") or 1
    status = _prompt("Status (Open/Closed/Filled)", default="Open")
    try:
        aid = svc.add_apprenticeship(
            title, employer_id, duration, description, salary, location,
            course, min_year, positions, status)
        print(f"\n✓ Added apprenticeship '{title}' (id={aid}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _update_apprenticeship(svc: ApprenticeshipService) -> None:
    aid = _prompt_int("Apprenticeship id", allow_blank=False)
    title = _prompt("Title")
    employer_id = _prompt_int("Employer id", allow_blank=False)
    duration = _prompt_int("Duration (months)", allow_blank=False)
    if not title or not duration:
        print("Title and duration are required.")
        return
    description = _prompt("Description (optional)")
    salary = _prompt_float("Salary (optional)")
    location = _prompt("Location (optional)")
    course = _prompt("Required course (optional)")
    min_year = _prompt_int("Min year (optional)") or 1
    positions = _prompt_int("Positions available (optional)") or 1
    status = _prompt("Status (Open/Closed/Filled)", default="Open")
    try:
        svc.update_apprenticeship(
            aid, title, employer_id, duration, description, salary, location,
            course, min_year, positions, status)
        print(f"\n✓ Updated apprenticeship {aid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _delete_apprenticeship(svc: ApprenticeshipService) -> None:
    aid = _prompt_int("Apprenticeship id", allow_blank=False)
    if _prompt("Delete this apprenticeship and its applications? (y/N)").lower() not in ("y", "yes"):
        print("Cancelled.")
        return
    try:
        svc.delete_apprenticeship(aid)
        print(f"\n✓ Deleted apprenticeship {aid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _apprenticeships_menu(svc: ApprenticeshipService, auth) -> None:
    while True:
        _header("Apprenticeship Listings")
        print("[1] List apprenticeships")
        print("[2] Add apprenticeship")
        print("[3] Update apprenticeship")
        print("[4] Delete apprenticeship")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_apprenticeships(svc)
        elif choice == "2":
            _add_apprenticeship(svc)
        elif choice == "3":
            _update_apprenticeship(svc)
        elif choice == "4":
            _delete_apprenticeship(svc)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 4. Applications
# --------------------------------------------------------------------------- #
def _list_applications(svc: ApprenticeshipService) -> None:
    status = _prompt("Status filter (Pending/Accepted/..., blank = all)")
    apps = svc.list_applications(status=status or None)
    if not apps:
        print("\nNo applications found.")
        return
    print(f"\n{'ID':<5}{'Student':<24}{'Apprenticeship':<26}{'Applied':<12}Status")
    print("-" * 80)
    for a in apps:
        applied = (a.get("application_date") or "")[:10]
        print(f"{a['id']:<5}{(a.get('student_name') or '')[:23]:<24}"
              f"{(a.get('title') or '')[:25]:<26}"
              f"{applied:<12}{a.get('status') or ''}")


def _submit_application(svc: ApprenticeshipService) -> None:
    student_id = _prompt("Student ID")
    apprenticeship_id = _prompt_int("Apprenticeship id", allow_blank=False)
    if not student_id or apprenticeship_id is None:
        print("Student ID and apprenticeship id are required.")
        return
    status = _prompt("Status", default="Pending")
    notes = _prompt("Notes (optional)")
    try:
        aid = svc.submit_application(student_id, apprenticeship_id, status, notes)
        print(f"\n✓ Submitted application {aid} for student {student_id}.")
    except sqlite3.IntegrityError:
        print("\n✗ This student has already applied to this apprenticeship.")
    except Exception as e:
        print(f"\n✗ {e}")


def _update_application_status(svc: ApprenticeshipService) -> None:
    aid = _prompt_int("Application id", allow_blank=False)
    status = _prompt("New status (Pending/Under Review/Interview/Accepted/Rejected/Withdrawn)")
    if not status:
        print("Status is required.")
        return
    notes = _prompt("Notes (blank to leave unchanged)")
    try:
        svc.update_application_status(aid, status, notes or None)
        print(f"\n✓ Updated application {aid} → {status}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _delete_application(svc: ApprenticeshipService) -> None:
    aid = _prompt_int("Application id", allow_blank=False)
    if _prompt("Delete this application? (y/N)").lower() not in ("y", "yes"):
        print("Cancelled.")
        return
    try:
        svc.delete_application(aid)
        print(f"\n✓ Deleted application {aid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _applications_menu(svc: ApprenticeshipService, auth) -> None:
    while True:
        _header("Applications")
        print("[1] List applications")
        print("[2] Submit application")
        print("[3] Update application status")
        print("[4] Delete application")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_applications(svc)
        elif choice == "2":
            _submit_application(svc)
        elif choice == "3":
            _update_application_status(svc)
        elif choice == "4":
            _delete_application(svc)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_apprenticeships_menu(auth) -> None:
    """Run the Apprenticeship Management CLI loop."""
    try:
        svc = ApprenticeshipService()
    except Exception as e:
        print(f"❌ Could not open the apprenticeship database: {e}")
        return
    try:
        while True:
            print("\n" + "=" * 50)
            print("    UNIVERSITY APPRENTICESHIP MANAGEMENT")
            print("=" * 50)
            print("1. Students")
            print("2. Employers")
            print("3. Apprenticeship Listings")
            print("4. Applications")
            print("5. Return to Main Menu")
            print("=" * 50)

            try:
                choice = input("\nEnter your choice (1-5): ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                return

            try:
                if choice == "1":
                    _students_menu(svc, auth)
                elif choice == "2":
                    _employers_menu(svc, auth)
                elif choice == "3":
                    _apprenticeships_menu(svc, auth)
                elif choice == "4":
                    _applications_menu(svc, auth)
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
        svc.close()
