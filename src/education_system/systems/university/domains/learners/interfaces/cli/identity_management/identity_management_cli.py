"""Console menu for controlled student identity changes — mirrors room_booking_cli.

Wraps ``domains.learners.application.identity_management``. Corrections,
merges and reversals are dual-control: the signed-in user is the requester
(or reverser) and a different approver must be named. Admin only.
"""
from __future__ import annotations

from typing import Any

from education_system.systems.university.domains.learners.application import identity_management
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


def _require_admin() -> bool:
    user = _current_user()
    if not user:
        print(get_text("cli.identity.login_required",
                       default="You must be logged in to access identity management."))
        return False
    if str(user.get("role", "")).lower() not in ("admin", "administrator"):
        print(get_text("cli.identity.admin_only",
                       default="Identity management is available to administrators only."))
        return False
    return True


def _lookup() -> None:
    student_id = input("Student ID: ").strip()
    try:
        record = identity_management.student_identity(student_id)
    except ValueError as exc:
        print(f"Error: {exc}")
        return
    for key, value in record.items():
        print(f"  {key:<14} {value}")
    changes = identity_management.list_identity_changes(student_id)
    print(f"\n  Identity changes ({len(changes)}):")
    for change in changes:
        print(f"    {str(change['created_at'] or '')[:19]:<20} {change['change_type']:<15} "
              f"{change['before_json']} -> {change['after_json']}  "
              f"[{change['requested_by']} / {change['approved_by']}]")


def _correct() -> None:
    student_id = input("Student ID: ").strip()
    print("Fields: " + ", ".join(sorted(identity_management.IDENTITY_FIELDS)))
    changes: dict[str, Any] = {}
    while True:
        field = input("Field to change (Enter to finish): ").strip()
        if not field:
            break
        changes[field] = input(f"New value for {field}: ").strip()
    reason = input("Reason: ").strip()
    approved_by = input("Approved by (must differ from you): ").strip()
    try:
        change_id = identity_management.correct_identity(
            student_id, changes, reason=reason, requested_by=_actor(), approved_by=approved_by,
        )
        print(f"Correction {change_id} applied.")
    except ValueError as exc:
        print(f"Error: {exc}")


def _list_merges() -> None:
    rows = identity_management.list_merges()
    if not rows:
        print(get_text("cli.identity.no_merges", default="No merges recorded."))
        return
    print(f"\n{'Merge ID':<38} {'Survivor':<10} {'Merged':<10} {'Status':<9} {'Requested/Approved':<26}")
    print("-" * 96)
    for row in rows:
        print(f"{row['merge_id']:<38} {str(row['survivor_id']):<10} {str(row['merged_id']):<10} "
              f"{row['status'] or '-':<9} {row['requested_by']} / {row['approved_by']}")
    print(f"\nTotal: {len(rows)}")


def _merge() -> None:
    survivor = input("Survivor student ID: ").strip()
    merged = input("Merged (duplicate) student ID: ").strip()
    reason = input("Reason: ").strip()
    approved_by = input("Approved by (must differ from you): ").strip()
    confirm = input(f"Mark {merged} as merged into {survivor}? (y/N): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return
    try:
        merge_id = identity_management.merge_students(
            survivor, merged, reason=reason, requested_by=_actor(), approved_by=approved_by,
        )
        print(f"Merge {merge_id} recorded.")
    except ValueError as exc:
        print(f"Error: {exc}")


def _reverse() -> None:
    merge_id = input("Merge ID: ").strip()
    reason = input("Reason: ").strip()
    try:
        identity_management.reverse_merge(merge_id, reversed_by=_actor(), reason=reason)
        print(f"Merge {merge_id} reversed.")
    except ValueError as exc:
        print(f"Error: {exc}")


def display_identity_management_menu() -> None:
    """Top-level identity management menu."""
    if not _require_admin():
        return
    actions = {
        "1": (get_text("cli.identity.lookup", default="Look Up Student"), _lookup),
        "2": (get_text("cli.identity.correct", default="Correct Identity"), _correct),
        "3": (get_text("cli.identity.merges", default="List Merges"), _list_merges),
        "4": (get_text("cli.identity.merge", default="Merge Students"), _merge),
        "5": (get_text("cli.identity.reverse", default="Reverse Merge"), _reverse),
    }
    while True:
        print("\n" + get_text("cli.identity.title", default="Student Identity Management"))
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
