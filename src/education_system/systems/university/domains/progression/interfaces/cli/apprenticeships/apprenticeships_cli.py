"""
University Apprenticeship Management — interactive CLI.

Employers and apprenticeship programmes are **owned by the apprenticeships
system** and read here through :mod:`apprenticeships_gateway`, a read-only
boundary mirroring ``apprenticeships.integrations.university_gateway``. This
menu shows what is on offer and records a student's application; creating or
editing employers and programmes happens in the apprenticeships system, so
there is one copy of each rather than two that drift.

Applications are recorded via ``ApprenticeshipService`` (shared
``student_records.db``) and routed by email to the employer's recorded
apprenticeship contact.

Student records are deliberately *not* managed here — the university already
has a student CRUD, and a second one only created a competing copy.
"""

from __future__ import annotations

import html
import logging
import sqlite3
from datetime import datetime
from typing import Optional

from education_system.systems.university.domains.progression.domain.apprenticeships.apprenticeship_service import (
    ApprenticeshipService,
)


# --------------------------------------------------------------------------- #
# Input helpers
# --------------------------------------------------------------------------- #
from education_system.systems.university.domains.progression.domain.apprenticeships.apprenticeships_gateway import (  # noqa: E501
    ApprenticeshipsGateway,
    ApprenticeshipsGatewayError,
)

logger = logging.getLogger(__name__)

_GATEWAY: ApprenticeshipsGateway | None = None


def _gateway() -> ApprenticeshipsGateway:
    """Read-only view onto the apprenticeships system (employers, programmes)."""
    global _GATEWAY
    if _GATEWAY is None:
        _GATEWAY = ApprenticeshipsGateway()
    return _GATEWAY


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
        logger.debug("Suppressed exception", exc_info=True)
    return "cli-user"


# --------------------------------------------------------------------------- #
# 1. Students
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# 2. Employers
# --------------------------------------------------------------------------- #
def _list_employers(svc: ApprenticeshipService) -> None:
    """Employers registered on the apprenticeships system.

    The apprenticeships system owns employer records; this is a read-only
    view of them, so a company appears here exactly once and is maintained
    in one place.
    """
    try:
        employers = _gateway().list_employers()
    except ApprenticeshipsGatewayError as e:
        print(f"\nApprenticeships system unavailable: {e}")
        return
    if not employers:
        print("\nNo employers are registered on the apprenticeships system.")
        return
    print(f"\n{'ID':<5}{'Company':<32}{'Sector':<28}{'Contact':<22}Email")
    print("-" * 110)
    for e in employers:
        print(f"{e.employer_id:<5}{(e.name or '')[:31]:<32}"
              f"{(e.sector or '-')[:27]:<28}"
              f"{(e.contact_name or '-')[:21]:<22}"
              f"{e.contact_email or '-'}")
    print(f"\n{len(employers)} employer(s). Maintained in the apprenticeships system.")


def _employers_menu(svc: ApprenticeshipService, auth) -> None:
    while True:
        _header("Employers")
        print("[1] List employers")
        print("[0] Back")
        print("\nEmployer records are owned by the apprenticeships system —")
        print("add or edit them there, not here.")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_employers(svc)
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
    """Apprenticeship standards offered by the apprenticeships system."""
    try:
        programmes = _gateway().list_programmes()
    except ApprenticeshipsGatewayError as e:
        print(f"\nApprenticeships system unavailable: {e}")
        return
    if not programmes:
        print("\nNo apprenticeship programmes are published yet.")
        return
    print(f"\n{'ID':<5}{'Ref':<9}{'Title':<46}{'Lvl':<5}{'Months':<8}Funding band")
    print("-" * 92)
    for p in programmes:
        band = f"£{p.funding_band:,.0f}" if p.funding_band else "-"
        print(f"{p.programme_id:<5}{(p.reference or '-')[:8]:<9}"
              f"{(p.title or '')[:45]:<46}"
              f"{p.level if p.level is not None else '-':<5}"
              f"{p.duration_months if p.duration_months is not None else '-':<8}{band}")
    print(f"\n{len(programmes)} programme(s). Maintained in the apprenticeships system.")


def _apprenticeships_menu(svc: ApprenticeshipService, auth) -> None:
    while True:
        _header("Apprenticeship Listings")
        print("[1] List apprenticeship programmes")
        print("[0] Back")
        print("\nProgrammes are owned by the apprenticeships system —")
        print("add or edit them there, not here.")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_apprenticeships(svc)
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


def _pick(label: str, options: list, describe) -> object | None:
    """Choose from a numbered list. Blank backs out."""
    if not options:
        print(f"\nNo {label}s are available.")
        return None
    print(f"\n{label.title()}s:")
    for index, option in enumerate(options, 1):
        print(f"  [{index}] {describe(option)}")
    while True:
        raw = input(f"Select {label} (blank to cancel): ").strip()
        if not raw:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print(f"Enter a number from 1 to {len(options)}.")


def _submit_application(svc: ApprenticeshipService) -> None:
    """Apply for an apprenticeship and route it to the employer's contact.

    The programme and employer both come from the apprenticeships system, so
    an application can only be made against something that really exists —
    and the notification goes to that employer's recorded apprenticeship
    contact rather than to nobody in particular.
    """
    student_id = _prompt("Student ID")
    if not student_id:
        return

    student = svc.get_student(student_id) if hasattr(svc, "get_student") else None

    try:
        gateway = _gateway()
        programmes = gateway.list_programmes(open_only=True)
        employers = gateway.list_employers(active_only=True)
    except ApprenticeshipsGatewayError as e:
        print(f"\nApprenticeships system unavailable: {e}")
        return

    programme = _pick(
        "programme", programmes,
        lambda p: f"{p.title} ({p.reference or '-'}, Level {p.level or '-'}, "
                  f"{p.duration_months or '-'} months)",
    )
    if programme is None:
        return

    employer = _pick(
        "employer", employers,
        lambda e: f"{e.name} — {e.sector or 'sector not recorded'}"
                  + (f" (contact: {e.contact_name})" if e.contact_name else " (no contact on file)"),
    )
    if employer is None:
        return

    notes = _prompt("Notes for the employer (optional)")

    try:
        aid = svc.submit_application(student_id, programme.programme_id,
                                     "Pending", notes,
                                     employer_id=employer.employer_id)
    except sqlite3.IntegrityError:
        print("\n✗ This student has already applied for that programme.")
        return
    except Exception as e:
        print(f"\n✗ {e}")
        return

    print(f"\n✓ Application {aid} recorded for {student_id}.")

    contact = gateway.employer_contact(employer.employer_id)
    if not contact:
        print(f"⚠ {employer.name} has no apprenticeship contact on the "
              f"apprenticeships system, so no notification could be sent.")
        print("  Add a primary manager for them there, then re-send.")
        return

    sent = _notify_employer(contact, employer, programme, student_id, student,
                            aid, notes)
    if sent:
        print(f"✓ Sent to {contact['full_name']} <{contact['email']}> "
              f"at {employer.name}.")
    else:
        print(f"⚠ Could not email {contact['email']}; the application is "
              f"still recorded.")


def _notify_employer(contact, employer, programme, student_id, student,
                     application_id, notes) -> bool:
    """Email the employer's apprenticeship contact. Never raises."""
    try:
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email,
        )
    except Exception:
        logger.warning("email infrastructure unavailable", exc_info=True)
        return False

    student_name = student_id
    student_email = ""
    if isinstance(student, dict):
        student_name = (
            f"{student.get('first_name', '')} {student.get('last_name', '')}".strip()
            or student_id
        )
        student_email = student.get("email") or ""

    try:
        subject, body = render_template(
            "academics/progression/apprenticeship_application_received",
            {
                "contact_name": html.escape(contact.get("full_name") or "Colleague"),
                "employer_name": html.escape(employer.name),
                "student_name": html.escape(student_name),
                "student_id": html.escape(str(student_id)),
                "student_email": html.escape(student_email or "(not on file)"),
                "application_reference": f"APP-{application_id}",
                "programme_title": html.escape(programme.title),
                "programme_reference": html.escape(programme.reference or "-"),
                "programme_level": str(programme.level or "-"),
                "duration_months": str(programme.duration_months or "-"),
                "applied_on": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "status": "Pending",
                "notes": html.escape(notes or "(none)"),
            },
        )
        if not subject or not body:
            logger.error("apprenticeship application template rendered nothing")
            return False
        send_email(recipient_email=contact["email"], subject=subject, body=body)
        return True
    except Exception:
        logger.warning("could not notify employer contact %s",
                       contact.get("email"), exc_info=True)
        return False


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
        print("[5] Submit apprenticeship experience as APL evidence")
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
        elif choice == "5":
            _submit_student_apl(svc)
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
            print("1. Employers")
            print("2. Apprenticeship Listings")
            print("3. Applications")
            print("4. Return to Main Menu")
            print("=" * 50)

            try:
                choice = input("\nEnter your choice (1-4): ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                return

            try:
                if choice == "1":
                    _employers_menu(svc, auth)
                elif choice == "2":
                    _apprenticeships_menu(svc, auth)
                elif choice == "3":
                    _applications_menu(svc, auth)
                elif choice == "4":
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
