"""
Health & Safety Portal — interactive CLI.

Wired to ``HSDatabase`` in ``health_safety.health_safety_service``, which
reads/writes the shared ``student_records.db`` — the same database the H&S
GUI (``health_safety_portal.py``) uses. Anything created here is visible in
the GUI and vice-versa.

Covers the persisted areas of the portal: Incidents (report / list / view /
update status), Hazards (report / list / mark completed), and Training
Records (list / record completion). Static resource pages and emergency
guidance are display-only and have no CLI surface.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from education_system.post_18.university_system.modules.domain.health.health_safety.health_safety_service import (
    HSDatabase,
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


def _db() -> HSDatabase:
    return HSDatabase()


def _ref(row: dict, prefix: str) -> str:
    return row.get("ref") or f"{prefix}-{row.get('id', 0):04d}"


# --------------------------------------------------------------------------- #
# 1. Incidents
# --------------------------------------------------------------------------- #
def _report_incident(auth) -> None:
    incident_type = _prompt("Incident type (e.g. slip, injury, near-miss)")
    description = _prompt("Description")
    if not incident_type or not description:
        print("Incident type and description are required.")
        return
    location = _prompt("Location (optional)")
    incident_date = _prompt("Incident date (YYYY-MM-DD)",
                            default=datetime.now().strftime("%Y-%m-%d"))
    severity = _prompt("Severity (Low/Medium/High/Critical)", default="Low")
    people = _prompt("People involved (optional)")
    actions = _prompt("Actions taken (optional)")
    department = _prompt("Department (optional)")
    data = {
        "incident_type": incident_type,
        "location": location,
        "incident_date": incident_date,
        "severity": severity,
        "people_involved": people,
        "description": description,
        "actions_taken": actions,
        "reported_by": _current_username(auth),
        "department": department,
        "status": "Open",
    }
    try:
        iid = _db().add_incident(data)
        print(f"\n✓ Reported H&S incident {iid} (ref INC-{iid:04d}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _list_incidents() -> None:
    try:
        rows = _db().list_incidents()
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not rows:
        print("\nNo incidents found.")
        return
    print(f"\n{'Ref':<12}{'Type':<16}{'Location':<18}{'Sev':<10}Status")
    print("-" * 68)
    for r in rows:
        print(f"{_ref(r, 'INC'):<12}"
              f"{(r.get('incident_type') or '')[:15]:<16}"
              f"{(r.get('location') or '')[:17]:<18}"
              f"{(r.get('severity') or '')[:9]:<10}"
              f"{r.get('status') or 'Open'}")


def _view_incident() -> None:
    iid = _prompt_int("Incident id (numeric)", allow_blank=False)
    try:
        rows = _db().list_incidents()
    except Exception as e:
        print(f"\n✗ {e}")
        return
    incident = next((r for r in rows if r.get("id") == iid), None)
    if not incident:
        print(f"\nNo incident with id {iid}.")
        return
    print(f"\n--- H&S Incident {iid} ({_ref(incident, 'INC')}) ---")
    for key in ("incident_type", "location", "incident_date", "severity",
                "people_involved", "description", "actions_taken",
                "reported_by", "department", "status", "reported_at",
                "updated_at"):
        print(f"  {key:<16}: {incident.get(key) or '-'}")


def _update_incident_status() -> None:
    iid = _prompt_int("Incident id (numeric)", allow_blank=False)
    status = _prompt("New status (Open/Under Investigation/Resolved/Closed)")
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
        _header("H&S Incidents")
        print("[1] Report incident")
        print("[2] List incidents")
        print("[3] View incident")
        print("[4] Update incident status")
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
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 2. Hazards
# --------------------------------------------------------------------------- #
def _report_hazard(auth) -> None:
    category = _prompt("Hazard category (e.g. electrical, trip, chemical)")
    description = _prompt("Description")
    if not category or not description:
        print("Category and description are required.")
        return
    location = _prompt("Location (optional)")
    risk_level = _prompt("Risk level (Low/Medium/High)", default="Medium")
    mitigation = _prompt("Proposed mitigation (optional)")
    department = _prompt("Department (optional)")
    data = {
        "category": category,
        "location": location,
        "risk_level": risk_level,
        "description": description,
        "mitigation": mitigation,
        "reported_by": _current_username(auth),
        "department": department,
        "status": "Active",
    }
    try:
        hid = _db().add_hazard(data)
        print(f"\n✓ Reported hazard {hid} (ref HAZ-{hid:04d}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _list_hazards() -> None:
    try:
        rows = _db().list_hazards()
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not rows:
        print("\nNo hazards found.")
        return
    print(f"\n{'Ref':<12}{'Category':<16}{'Location':<18}{'Risk':<10}Status")
    print("-" * 68)
    for r in rows:
        print(f"{_ref(r, 'HAZ'):<12}"
              f"{(r.get('category') or '')[:15]:<16}"
              f"{(r.get('location') or '')[:17]:<18}"
              f"{(r.get('risk_level') or '')[:9]:<10}"
              f"{r.get('status') or 'Active'}")


def _complete_hazard() -> None:
    hid = _prompt_int("Hazard id (numeric) to mark Completed", allow_blank=False)
    try:
        if _db().update_hazard_status(hid, "Completed"):
            print(f"\n✓ Marked hazard {hid} as Completed.")
        else:
            print(f"\nNo hazard with id {hid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _hazards_menu(auth) -> None:
    while True:
        _header("H&S Hazards")
        print("[1] Report hazard")
        print("[2] List hazards")
        print("[3] Mark hazard completed")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _report_hazard(auth)
        elif choice == "2":
            _list_hazards()
        elif choice == "3":
            _complete_hazard()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 3. Training Records
# --------------------------------------------------------------------------- #
def _list_training() -> None:
    try:
        rows = _db().list_training()
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not rows:
        print("\nNo training records found.")
        return
    print(f"\n{'ID':<5}{'User':<18}{'Module':<30}{'Dept':<14}Completed")
    print("-" * 84)
    for r in rows:
        print(f"{r['id']:<5}{(r.get('user') or '')[:17]:<18}"
              f"{(r.get('module') or '')[:29]:<30}"
              f"{(r.get('department') or '')[:13]:<14}"
              f"{(r.get('completed_at') or '')[:19]}")


def _record_training(auth) -> None:
    module = _prompt("Training module completed")
    if not module:
        print("Module is required.")
        return
    user = _prompt("User", default=_current_username(auth))
    department = _prompt("Department (optional)")
    data = {"user": user, "module": module, "department": department}
    try:
        tid = _db().add_training(data)
        print(f"\n✓ Recorded training completion {tid} for '{user}'.")
    except Exception as e:
        print(f"\n✗ {e}")


def _training_menu(auth) -> None:
    while True:
        _header("H&S Training Records")
        print("[1] List training records")
        print("[2] Record training completion")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_training()
        elif choice == "2":
            _record_training(auth)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_health_safety_menu(auth) -> None:
    """Run the Health & Safety Portal CLI loop."""
    while True:
        print("\n" + "=" * 50)
        print("     HEALTH & SAFETY PORTAL")
        print("=" * 50)
        print("1. Incidents")
        print("2. Hazards")
        print("3. Training Records")
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
                _hazards_menu(auth)
            elif choice == "3":
                _training_menu(auth)
            elif choice == "4":
                print("Returning to main menu...")
                return
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:  # keep the menu resilient
            print(f"❌ Error: {e}")
