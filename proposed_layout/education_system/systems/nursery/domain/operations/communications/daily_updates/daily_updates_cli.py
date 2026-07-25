"""CLI flow for Daily Updates (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.operations.communications.daily_updates import (
    daily_updates as data,
)
from education_system.systems.nursery.domain.operations.communications.daily_updates.daily_updates import (
    MOODS,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _yn(flag: bool) -> str:
    return "Yes" if flag else ""


def _print_table(rows: list[data.DailyUpdate]) -> None:
    if not rows:
        print("  (no daily updates)")
        return
    print(f"  {'ID':<8} {'Child':<20} {'Date':<12} {'Mood':<12} "
          f"{'Sleep':<16} {'Shared'}")
    print(f"  {'-'*8} {'-'*20} {'-'*12} {'-'*12} {'-'*16} {'-'*6}")
    for u in rows:
        print(f"  {u.update_id:<8} {(u.child_name or '-')[:20]:<20} "
              f"{(u.update_date or '-'):<12} {(u.mood or '-')[:12]:<12} "
              f"{(u.sleep or '-')[:16]:<16} {_yn(u.shared)}")


def _print_detail(u: data.DailyUpdate) -> None:
    print(f"\n  ── Daily Update {u.update_id} ──")
    print(f"  Child:       {u.child_name or '-'} ({u.pupil_id})")
    print(f"  Date:        {u.update_date or '-'}")
    print(f"  Mood:        {u.mood or '-'}")
    print(f"  Meals:       {u.meals or '-'}")
    print(f"  Sleep:       {u.sleep or '-'}")
    print(f"  Nappies:     {u.nappies or '-'}")
    print(f"  Activities:  {u.activities or '-'}")
    print(f"  Notes:       {u.notes or '-'}")
    print(f"  Staff:       {u.staff_name or (u.staff_id or '-')}")
    print(f"  Shared:      {'Yes' if u.shared else 'No'}")


def _show_children() -> None:
    try:
        choices = data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return
    if choices:
        print("  Children:")
        for _id, label in choices:
            print(f"    {label}")


def _show_staff() -> None:
    try:
        choices = data.list_staff_choices()
    except Exception:
        logger.exception("Could not load staff choices")
        return
    if choices:
        print("  Staff:")
        for _id, label in choices:
            print(f"    {label}")


def _ask_bool(label: str, current: bool | None) -> str:
    cur = "" if current is None else ("y" if current else "n")
    suffix = f" [{cur}]" if cur else ""
    v = _prompt(f"  {label} (y/n){suffix}: ").lower()
    return v if v else cur


def _collect_fields(existing: data.DailyUpdate | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id

    fields["update_date"] = ask("Date (YYYY-MM-DD)",
                                existing.update_date if existing else None)
    fields["mood"] = ask(f"Mood ({'/'.join(MOODS)})",
                         existing.mood if existing else None)
    fields["meals"] = ask("Meals", existing.meals if existing else None)
    fields["sleep"] = ask("Sleep", existing.sleep if existing else None)
    fields["nappies"] = ask("Nappies", existing.nappies if existing else None)
    fields["activities"] = ask("Activities", existing.activities if existing else None)
    fields["notes"] = ask("Notes", existing.notes if existing else None)
    fields["staff_id"] = ask("Staff ID", existing.staff_id if existing else None)
    fields["shared"] = _ask_bool("Share with parent?",
                                 existing.shared if existing else False)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: daily_updates open_manager")
    while True:
        print("\n  ── Daily Updates ──")
        _print_table(data.list_updates())
        print("\n   A) Add    V) View    E) Edit    D) Delete")
        print("   C) Updates for a child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            uid = _prompt("  Update ID: ")
            u = data.get_update(uid)
            if u is None:
                print("  No update with that ID.")
            else:
                _print_detail(u)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "c":
            pid = _prompt("  Child ID: ")
            _print_table(data.list_updates(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Daily Update ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    _show_staff()
    fields = _collect_fields(pupil_id=pid)
    u = data.create_update(fields)
    print(f"\n  Added daily update {u.update_id} for "
          f"{u.child_name or pid} on {u.update_date or '(no date)'}.")


@_safe
def open_edit() -> None:
    uid = _prompt("  Update ID: ")
    if not uid:
        print("  Cancelled.")
        return
    existing = data.get_update(uid)
    if existing is None:
        print("  No update with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    _show_staff()
    fields = _collect_fields(existing)
    u = data.update_update(uid, fields)
    print(f"\n  Updated daily update {u.update_id}.")


@_safe
def open_delete() -> None:
    uid = _prompt("  Update ID to delete: ")
    if not uid:
        print("  Cancelled.")
        return
    existing = data.get_update(uid)
    if existing is None:
        print("  No update with that ID.")
        return
    label = f"{existing.child_name or existing.pupil_id} — {existing.update_date or 'no date'}"
    if _prompt(f"  Delete update {uid} ({label})? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_update(uid):
        print(f"  Deleted daily update {uid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Daily Updates": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching daily_updates CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
