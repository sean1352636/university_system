"""Console menu for institution-wide timetabling — mirrors room_booking_cli.

Wraps ``domains.academics.application.timetabling``: build a draft version
from activities/slots/rooms, publish it (superseding the live one) and log
change requests against a version. Staff only.
"""
from __future__ import annotations

import json
from typing import Any

from education_system.systems.university.domains.academics.application import timetabling
from education_system.systems.university.infrastructure.i18n import get_text

auth: Any = None


def set_auth(auth_object: Any) -> None:
    global auth
    auth = auth_object


def _current_user() -> dict[str, Any] | None:
    return getattr(auth, "current_user", None) if auth else None


def _actor() -> str:
    user = _current_user() or {}
    return str(user.get("username") or user.get("id") or "unknown")


def _require_staff() -> bool:
    user = _current_user()
    if not user:
        print(get_text("cli.timetabling.login_required",
                       default="You must be logged in to access timetabling."))
        return False
    if str(user.get("role", "")).lower() not in ("admin", "administrator", "staff"):
        print(get_text("cli.timetabling.staff_only",
                       default="Timetabling is available to staff only."))
        return False
    return True


def _list_versions() -> None:
    rows = timetabling.list_versions()
    if not rows:
        print(get_text("cli.timetabling.none", default="No timetable versions."))
        return
    print(f"\n{'Version ID':<38} {'Year':<9} {'Status':<11} {'Created by':<14} {'Created':<20}")
    print("-" * 95)
    for row in rows:
        print(f"{row['version_id']:<38} {row['academic_year'] or '-':<9} "
              f"{row['status'] or '-':<11} {str(row['created_by'] or '-')[:14]:<14} "
              f"{str(row['created_at'] or '-')[:19]:<20}")
    print(f"\nTotal: {len(rows)}")


def _print_schedule(schedule: list[dict[str, Any]]) -> None:
    if not schedule:
        print(get_text("cli.timetabling.empty_schedule", default="(empty schedule)"))
        return
    print(f"\n{'Activity':<16} {'Slot':<10} {'Room':<8} {'Staff':<10} {'Cohorts'}")
    print("-" * 70)
    for item in schedule:
        print(f"{str(item.get('activity_id') or '-'):<16} {str(item.get('slot')):<10} "
              f"{str(item.get('room')):<8} {str(item.get('staff_id') or '-'):<10} "
              f"{', '.join(item.get('cohorts') or [])}")


def _view_version() -> None:
    version_id = input("Version ID: ").strip()
    try:
        record = timetabling.version_record(version_id)
    except ValueError as exc:
        print(f"Error: {exc}")
        return
    schedule = record.pop("schedule")
    for key, value in record.items():
        print(f"  {key:<14} {value}")
    _print_schedule(schedule)
    requests = timetabling.list_change_requests(version_id)
    print(f"\n  Change requests ({len(requests)}):")
    for req in requests:
        print(f"    {req['request_id']}  {req['status']:<9} {req['requested_by'] or '-':<12} {req['reason']}")


def _published() -> None:
    _print_schedule(timetabling.published_schedule())


def _build_version() -> None:
    print("Activities as a JSON list, e.g.\n"
          '  [{"activity_id": "A", "staff_id": "T1", "cohorts": ["C1"], "allowed_slots": ["MON-09"]}]')
    raw = input("Activities JSON: ").strip()
    slots = [s.strip() for s in input("Slots (comma-separated): ").split(",") if s.strip()]
    rooms = [r.strip() for r in input("Rooms (comma-separated): ").split(",") if r.strip()]
    year = input("Academic year (e.g. 2027/28): ").strip()
    try:
        activities = json.loads(raw)
        if not isinstance(activities, list):
            raise ValueError("Activities must be a JSON list")
        version_id = timetabling.optimise(
            activities, slots, rooms, academic_year=year, created_by=_actor(),
        )
        print(f"Draft version {version_id} created.")
    except (ValueError, TypeError) as exc:
        print(f"Error: {exc}")


def _publish() -> None:
    version_id = input("Version ID to publish: ").strip()
    confirm = input("Publishing supersedes the live timetable. Continue? (y/N): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return
    try:
        timetabling.publish(version_id, approved_by=_actor())
        print(f"Version {version_id} published.")
    except ValueError as exc:
        print(f"Error: {exc}")


def _request_change() -> None:
    version_id = input("Version ID: ").strip()
    reason = input("Reason: ").strip()
    raw = input('Proposed change JSON (e.g. {"activity_id": "A", "slot": "TUE-09"}): ').strip()
    try:
        proposed = json.loads(raw or "{}")
        if not isinstance(proposed, dict):
            raise ValueError("Proposed change must be a JSON object")
        request_id = timetabling.request_change(
            version_id, proposed, reason=reason, requested_by=_actor(),
        )
        print(f"Change request {request_id} logged.")
    except (ValueError, TypeError) as exc:
        print(f"Error: {exc}")


def display_timetabling_menu() -> None:
    """Top-level timetabling menu."""
    if not _require_staff():
        return
    actions = {
        "1": (get_text("cli.timetabling.list", default="List Versions"), _list_versions),
        "2": (get_text("cli.timetabling.view", default="View Version"), _view_version),
        "3": (get_text("cli.timetabling.published", default="Published Schedule"), _published),
        "4": (get_text("cli.timetabling.build", default="Build Draft Version"), _build_version),
        "5": (get_text("cli.timetabling.publish", default="Publish Version"), _publish),
        "6": (get_text("cli.timetabling.request_change", default="Request Change"), _request_change),
    }
    while True:
        print("\n" + get_text("cli.timetabling.title", default="Institutional Timetabling"))
        print("=" * 30)
        for key, (label, _) in actions.items():
            print(f"{key}. {label}")
        print("0. " + get_text("cli.menu.return", default="Return to Previous Menu"))
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if not action:
            print(get_text("cli.invalid_choice", default="Invalid choice."))
            continue
        try:
            action[1]()
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as exc:  # the tables may be missing on a fresh DB
            print(f"Error: {exc}")
