"""Console menu for the shared case register — mirrors room_booking_cli.

Appeals, complaints, misconduct, fitness to practise and mitigating
circumstances all share one register (``application.case_management``).
Staff only: every action records the signed-in user as the actor.
"""
from __future__ import annotations

from typing import Any

from education_system.systems.university.application import case_management
from education_system.systems.university.infrastructure.i18n import get_text

auth: Any = None

STATUSES = ("open", "triage", "investigation", "hearing", "decision", "review", "closed")


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
        print(get_text("cli.case_management.login_required",
                       default="You must be logged in to access case management."))
        return False
    if str(user.get("role", "")).lower() not in ("admin", "administrator", "staff"):
        print(get_text("cli.case_management.staff_only",
                       default="Case management is available to staff only."))
        return False
    return True


def _print_cases(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print(get_text("cli.case_management.none", default="No cases found."))
        return
    print(f"\n{'Case ID':<38} {'Type':<24} {'Subject':<10} {'Status':<14} {'Opened':<20}")
    print("-" * 108)
    for case in rows:
        print(f"{case['case_id']:<38} {case['case_type']:<24} "
              f"{str(case['subject_id'] or '-')[:10]:<10} "
              f"{case['status'] or '-':<14} {str(case['opened_at'] or '-')[:19]:<20}")
    print(f"\nTotal: {len(rows)}")


def _list_cases() -> None:
    case_type = input("Filter by type (Enter for all): ").strip() or None
    status = input("Filter by status (Enter for all): ").strip() or None
    try:
        _print_cases(case_management.list_cases(case_type=case_type, status=status))
    except Exception as exc:  # the register may be missing on a fresh DB
        print(f"Error: {exc}")


def _view_case() -> None:
    case_id = input("Case ID: ").strip()
    try:
        record = case_management.case_record(case_id)
    except ValueError as exc:
        print(f"Error: {exc}")
        return
    events = record.pop("events", [])
    for key, value in record.items():
        print(f"  {key:<16} {value}")
    print(f"\n  Events ({len(events)}):")
    for event in events:
        print(f"    {str(event.get('created_at') or '')[:19]:<20} "
              f"{event.get('event_type'):<28} {event.get('actor_id') or '-'}  "
              f"{event.get('payload_json') or ''}")


def _open_case() -> None:
    print("Types: " + ", ".join(sorted(case_management.CASE_TYPES)))
    case_type = input("Case type: ").strip()
    subject_id = input("Subject (student/staff id): ").strip()
    summary = input("Summary: ").strip()
    confidentiality = input("Confidentiality [restricted]: ").strip() or "restricted"
    owner_id = input("Owner id (Enter for none): ").strip() or None
    try:
        case_id = case_management.open_case(
            case_type, subject_id, summary, opened_by=_actor(),
            confidentiality=confidentiality, owner_id=owner_id,
        )
        print(f"Case {case_id} opened.")
    except ValueError as exc:
        print(f"Error: {exc}")


def _transition_case() -> None:
    case_id = input("Case ID: ").strip()
    print("Statuses: " + ", ".join(STATUSES))
    status = input("New status: ").strip()
    reason = input("Reason: ").strip()
    try:
        case_management.transition_case(case_id, status, actor_id=_actor(), reason=reason)
        print(f"Case {case_id} moved to {status}.")
    except ValueError as exc:
        print(f"Error: {exc}")


def _appeals() -> None:
    from education_system.systems.university.domains.governance.interfaces.cli.case_management import (  # noqa: E501
        appeals_cli,
    )
    appeals_cli.set_auth(auth)
    appeals_cli.display_appeals_menu()


def display_case_management_menu() -> None:
    """Top-level case register menu."""
    if not _require_staff():
        return
    actions = {
        "1": (get_text("cli.case_management.list", default="List Cases"), _list_cases),
        "2": (get_text("cli.case_management.view", default="View Case"), _view_case),
        "3": (get_text("cli.case_management.open", default="Open Case"), _open_case),
        "4": (get_text("cli.case_management.transition", default="Change Status"), _transition_case),
        "5": (get_text("cli.case_management.appeals", default="Academic Appeals"), _appeals),
    }
    while True:
        print("\n" + get_text("cli.case_management.title", default="Case Management"))
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
