"""
First Aid Portal — interactive CLI.

Wired to ``IncidentDB`` in ``first_aid.first_aid_service``, which reads/
writes the shared ``student_records.db`` — the same database the First Aid
GUI (``first_aid_portal.py``) uses. Anything created here is visible in the
GUI and vice-versa.

Covers the persisted areas of the portal: Incident Reports (report / list /
view / update status / mark resolved), First Aid Training Registrations
(list / register), and the Emergency Contact directory (read-only reference
data shared with the GUI). Static guidance pages (guides, videos, external
links) are display-only and have no CLI surface.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

from datetime import datetime
from typing import Optional

from education_system.systems.university.domains.health.domain.health.first_aid.first_aid_service import (
    EMERGENCY_CONTACTS,
    IncidentDB,
    emergency_contacts,
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
        logger.debug("Suppressed exception", exc_info=True)
    return "cli-user"


def _db() -> IncidentDB:
    return IncidentDB()


def _rules():
    from education_system.systems.university.domains.health.application.health import (
        first_aid,
    )
    return first_aid


def _who(auth):
    from education_system.systems.university.domains.health.application.health import access
    user = getattr(auth, "current_user", None)
    return access.from_user(user if isinstance(user, dict) else None)


def _write(fn, *args, **kwargs):
    """Run a first aid rule in one transaction; send any e-mails after."""
    from education_system.systems.university.domains.health.infrastructure.health.storage import (
        get_connection,
    )
    _db()                                   # schema
    conn = get_connection()
    try:
        result = fn(conn, *args, **kwargs)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if isinstance(result, list) and result and isinstance(result[0], tuple):
        from education_system.systems.university.infrastructure.ui.record_screens import (
            send_emails,
        )
        send_emails(result)
    return result


def _read(fn, *args, **kwargs):
    from education_system.systems.university.domains.health.infrastructure.health.storage import (
        get_connection,
    )
    _db()
    conn = get_connection()
    try:
        return fn(conn, *args, **kwargs)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# 1. Incident Reports
# --------------------------------------------------------------------------- #
def _report_incident(auth) -> None:
    reporter_name = _prompt("Reporter name")
    description = _prompt("Description of incident")
    if not reporter_name or not description:
        print("Reporter name and description are required.")
        return
    reporter_id = _prompt("Reporter id (student/staff id, optional)")
    phone = _prompt("Phone (optional)")
    email = _prompt("Email (optional)")
    location = _prompt("Location (optional)")
    incident_type = _prompt("Incident type (e.g. injury, illness)", default="injury")
    severity = _prompt("Severity (Low/Medium/High/Critical)", default="Low")
    incident_date = _prompt("Date it happened (YYYY-MM-DD)",
                            default=datetime.now().strftime("%Y-%m-%d"))
    person = _prompt("Person affected: worker or non_worker (student/visitor)",
                     default="non_worker")
    report = {
        "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "reporter_user": _current_username(auth),
        "reporter_name": reporter_name,
        "reporter_id": reporter_id,
        "phone": phone,
        "email": email,
        "location": location,
        "incident_type": incident_type,
        "severity": severity,
        "description": description,
        "status": "Open",
        "incident_date": incident_date,
        "person_type": person if person in ("worker", "non_worker") else None,
    }
    try:
        iid = _db().add(report)
        print(f"\n✓ Reported first-aid incident {iid} (by {report['reporter_user']}).")
        if severity.lower() in ("high", "critical", "severe"):
            print("  Opened as a Health & Safety incident; assess it for RIDDOR (menu 7).")
    except Exception as e:
        print(f"\n✗ {e}")


def _health_team(auth) -> bool:
    who = _who(auth)
    return bool(who and who.is_clinician)


def _list_incidents(auth=None) -> None:
    severity = _prompt("Severity filter (Low/Medium/High/Critical, blank = all)")
    status = _prompt("Status filter (Open/Resolved, blank = all)")
    # Archived incidents are hidden; the health team may include them.
    archived = _health_team(auth) and _prompt(
        "Include archived incidents? (y/N)").strip().lower() == "y"
    try:
        rows = _db().fetch_all(severity=severity or None, status=status or None,
                               include_archived=archived)
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not rows:
        print("\nNo incidents found.")
        return
    rules = _rules()
    print(f"\n{'ID':<5}{'When':<20}{'Reporter':<18}{'Type':<12}{'Sev':<10}{'Status':<10}RIDDOR")
    print("-" * 100)
    for r in rows:
        print(f"{r['id']:<5}{(r.get('submitted_at') or '')[:19]:<20}"
              f"{(r.get('reporter_name') or '')[:17]:<18}"
              f"{(r.get('incident_type') or '')[:11]:<12}"
              f"{(r.get('severity') or '')[:9]:<10}"
              f"{(r.get('status') or 'Open')[:9]:<10}"
              f"{rules.riddor_state(r)}"
              f"{'  [archived]' if r.get('archived') else ''}")


def _view_incident(auth=None) -> None:
    iid = _prompt_int("Incident id", allow_blank=False)
    try:
        rows = _db().fetch_all(include_archived=_health_team(auth))
    except Exception as e:
        print(f"\n✗ {e}")
        return
    incident = next((r for r in rows if r.get("id") == iid), None)
    if not incident:
        print(f"\nNo incident with id {iid}.")
        return
    print(f"\n--- First Aid Incident {iid} ---")
    for key in ("submitted_at", "reporter_name", "reporter_id", "reporter_user",
                "phone", "email", "location", "incident_type", "severity",
                "status", "description", "incident_date", "person_type",
                "riddor_category", "riddor_deadline", "hse_reference", "hs_incident_id"):
        print(f"  {key:<15}: {incident.get(key) or '-'}")
    if incident.get("archived"):
        print(f"  {'archived':<15}: {incident.get('archived_at') or '-'} by "
              f"{incident.get('archived_by') or '-'} ({incident.get('archive_reason') or '-'})")
    print(f"  {'RIDDOR':<15}: {_rules().riddor_state(incident)}")


def _riddor_queue() -> None:
    rules = _rules()
    rows = _read(rules.riddor_queue)
    summary = _read(rules.riddor_summary)
    print(f"\nOverdue: {summary['overdue']}   Due within {rules.DUE_SOON_DAYS} days: "
          f"{summary['due_soon']}   Reported: {summary['by_status'].get('reported', 0)}")
    if not rows:
        print("\nNothing waiting for RIDDOR assessment or reporting.")
        return
    for r in rows:
        print(f"  INC-{r['id']:04d}  {(r.get('incident_date') or r['submitted_at'])[:10]}  "
              f"{(r.get('location') or '-')[:20]:<20}  {r.get('severity') or '-':<9}  "
              f"{r['riddor_state']}")


def _assess_riddor(auth) -> None:
    rules = _rules()
    iid = _prompt_int("Incident id", allow_blank=False)
    print("Person: " + ", ".join(rules.PERSON_TYPES))
    person = _prompt("Person type", default="non_worker")
    for key, label in rules.CATEGORIES.items():
        print(f"  {key:<22} {label}")
    category = _prompt("Category", default="not_reportable")
    notes = _prompt("Notes (optional)")
    try:
        result = _write(rules.assess_riddor, _who(auth), iid, person_type=person,
                        category=category, notes=notes)
    except (PermissionError, ValueError) as e:
        print(f"\n✗ {e}")
        return
    if result["status"] == "reportable":
        print(f"\n⚠ Reportable: report to the HSE by {result['deadline']} "
              "(deaths/specified injuries without delay).")
    else:
        print(f"\n✓ {result['status'].replace('_', ' ').capitalize()}.")


def _record_hse_report(auth) -> None:
    iid = _prompt_int("Incident id", allow_blank=False)
    reference = _prompt("HSE reference")
    reported_on = _prompt("Reported on (YYYY-MM-DD)", default=datetime.now().strftime("%Y-%m-%d"))
    try:
        _write(_rules().mark_reported, _who(auth), iid, reference, reported_on)
        print(f"\n✓ INC-{iid:04d} recorded as reported ({reference}).")
    except (PermissionError, ValueError) as e:
        print(f"\n✗ {e}")


def _update_incident_status() -> None:
    iid = _prompt_int("Incident id", allow_blank=False)
    status = _prompt("New status (Open/In Progress/Resolved)")
    if not status:
        print("Status is required.")
        return
    try:
        if _db().update_status(iid, status):
            print(f"\n✓ Updated incident {iid} → {status}.")
        else:
            print(f"\nNo incident with id {iid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _mark_resolved() -> None:
    iid = _prompt_int("Incident id to mark Resolved", allow_blank=False)
    try:
        if _db().update_status(iid, "Resolved"):
            print(f"\n✓ Marked incident {iid} as Resolved.")
        else:
            print(f"\nNo incident with id {iid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _incidents_menu(auth) -> None:
    while True:
        _header("First Aid Incident Reports")
        print("[1] Report incident")
        print("[2] List incidents")
        print("[3] View incident")
        print("[4] Update incident status")
        print("[5] Mark incident resolved")
        print("[6] RIDDOR queue")
        print("[7] Assess incident for RIDDOR")
        print("[8] Record HSE report")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _report_incident(auth)
        elif choice == "2":
            _list_incidents(auth)
        elif choice == "3":
            _view_incident(auth)
        elif choice == "4":
            _update_incident_status()
        elif choice == "5":
            _mark_resolved()
        elif choice == "6":
            _riddor_queue()
        elif choice == "7":
            _assess_riddor(auth)
        elif choice == "8":
            _record_hse_report(auth)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 2. Training Registrations
# --------------------------------------------------------------------------- #
def _list_registrations() -> None:
    try:
        regs = _db().fetch_registrations()
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not regs:
        print("\nNo training registrations found.")
        return
    print(f"\n{'ID':<5}{'When':<20}{'Course':<26}{'Name':<20}Preferred")
    print("-" * 82)
    for r in regs:
        print(f"{r['id']:<5}{(r.get('submitted_at') or '')[:19]:<20}"
              f"{(r.get('course') or '')[:25]:<26}"
              f"{(r.get('name') or '')[:19]:<20}"
              f"{r.get('preferred_date') or '-'}")


def _register_training(auth) -> None:
    course = _prompt("Course name")
    name = _prompt("Registrant name")
    if not course or not name:
        print("Course and name are required.")
        return
    email = _prompt("Email (optional)")
    phone = _prompt("Phone (optional)")
    sessions = _read(_rules().sessions, course=course) or _read(_rules().sessions)
    session = None
    if sessions:
        print("\nScheduled sessions:")
        for x in sessions:
            print(f"  [{x['id']}] {str(x['starts_at'])[:16]}  {x['course']}  "
                  f"{x.get('location') or ''}  ({x['places_left']} left)")
        pick = _prompt_int("Session id (blank = no date yet)")
        if pick is not None:
            try:
                session = _read(_rules().check_booking, pick, _current_username(auth), email)
            except ValueError as e:
                print(f"\n✗ {e}")
                return
    else:
        print("\nNo sessions are scheduled; you will be contacted when one is.")
    preferred = str(session["starts_at"]) if session else ""
    notes = _prompt("Notes (optional)")
    reg = {
        "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "course": course,
        "user_id": _current_username(auth),
        "name": name,
        "email": email,
        "phone": phone,
        "preferred_date": preferred,
        "notes": notes,
        "session_id": session["id"] if session else None,
    }
    if session:
        reg["course"] = session["course"]
    try:
        rid = _db().add_registration(reg)
        print(f"\n✓ Registered '{name}' for '{course}' (id={rid}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _training_menu(auth) -> None:
    while True:
        _header("First Aid Training Registrations")
        print("[1] List registrations")
        print("[2] Register for a course")
        print("[3] Upcoming course sessions")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_registrations()
        elif choice == "2":
            _register_training(auth)
        elif choice == "3":
            for x in _read(_rules().sessions) or []:
                print(f"  [{x['id']}] {str(x['starts_at'])[:16]}  {x['course']}  "
                      f"{x.get('location') or ''}  {x['booked']}/{x['capacity']} booked")
            if not _read(_rules().sessions):
                print("\nNo sessions scheduled.")
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 3. Emergency Contacts (read-only reference directory)
# --------------------------------------------------------------------------- #
def _list_emergency_contacts() -> None:
    _header("Emergency Contact Directory")
    for c in emergency_contacts():
        print(f"\n  {c.get('icon', '')} {c.get('name')}")
        print(f"     Number   : {c.get('number')}")
        print(f"     Location : {c.get('location')}")
        print(f"     {c.get('description')}")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_first_aid_menu(auth) -> None:
    """Run the First Aid Portal CLI loop."""
    while True:
        print("\n" + "=" * 50)
        print("       FIRST AID PORTAL")
        print("=" * 50)
        print("1. Incident Reports")
        print("2. Training Registrations")
        print("3. Emergency Contacts")
        print("4. Return to Main Menu")
        print("=" * 50)

        try:
            choice = input("\nEnter your choice (1-4): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        try:
            if choice == "1":
                _incidents_menu(auth)
            elif choice == "2":
                _training_menu(auth)
            elif choice == "3":
                _list_emergency_contacts()
                _pause()
            elif choice == "4":
                print("Returning to main menu...")
                return
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:  # keep the menu resilient
            print(f"❌ Error: {e}")
