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

from datetime import datetime
from typing import Optional

from education_system.systems.university.domain.pastoral.health.first_aid.first_aid_service import (
    EMERGENCY_CONTACTS,
    IncidentDB,
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


def _db() -> IncidentDB:
    return IncidentDB()


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
    }
    try:
        iid = _db().add(report)
        print(f"\n✓ Reported first-aid incident {iid} (by {report['reporter_user']}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _list_incidents() -> None:
    severity = _prompt("Severity filter (Low/Medium/High/Critical, blank = all)")
    status = _prompt("Status filter (Open/Resolved, blank = all)")
    try:
        rows = _db().fetch_all(severity=severity or None, status=status or None)
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not rows:
        print("\nNo incidents found.")
        return
    print(f"\n{'ID':<5}{'When':<20}{'Reporter':<18}{'Type':<12}{'Sev':<10}Status")
    print("-" * 78)
    for r in rows:
        print(f"{r['id']:<5}{(r.get('submitted_at') or '')[:19]:<20}"
              f"{(r.get('reporter_name') or '')[:17]:<18}"
              f"{(r.get('incident_type') or '')[:11]:<12}"
              f"{(r.get('severity') or '')[:9]:<10}"
              f"{r.get('status') or 'Open'}")


def _view_incident() -> None:
    iid = _prompt_int("Incident id", allow_blank=False)
    try:
        rows = _db().fetch_all()
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
                "status", "description"):
        print(f"  {key:<15}: {incident.get(key) or '-'}")


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
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _report_incident(auth)
        elif choice == "2":
            _list_incidents()
        elif choice == "3":
            _view_incident()
        elif choice == "4":
            _update_incident_status()
        elif choice == "5":
            _mark_resolved()
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
    preferred = _prompt("Preferred date (YYYY-MM-DD, optional)")
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
    }
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
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_registrations()
        elif choice == "2":
            _register_training(auth)
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
    for c in EMERGENCY_CONTACTS:
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
