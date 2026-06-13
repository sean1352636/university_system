"""CLI flow for Parent Meetings (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.parent_meetings import (
    parent_meetings as data,
)
from education_system.nursery_system.modules.domain.parent_meetings.parent_meetings import (
    MEETING_TYPES,
    STATUSES,
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


def _print_table(rows: list[data.Meeting]) -> None:
    if not rows:
        print("  (no parent meetings)")
        return
    print(f"  {'ID':<8} {'Child':<20} {'Date':<12} {'Time':<7} "
          f"{'Type':<22} {'Status':<12} {'Staff'}")
    print(f"  {'-'*8} {'-'*20} {'-'*12} {'-'*7} {'-'*22} {'-'*12} {'-'*20}")
    for m in rows:
        print(f"  {m.meeting_id:<8} {(m.child_name or '-')[:20]:<20} "
              f"{(m.meeting_date or '-'):<12} {(m.meeting_time or '-')[:7]:<7} "
              f"{(m.meeting_type or '-')[:22]:<22} {m.status[:12]:<12} "
              f"{(m.staff_name or '-')[:20]}")


def _print_detail(m: data.Meeting) -> None:
    print(f"\n  ── Parent meeting {m.meeting_id} ──")
    print(f"  Child:         {m.child_name or '-'} ({m.pupil_id})")
    print(f"  Date:          {m.meeting_date or '-'}")
    print(f"  Time:          {m.meeting_time or '-'}")
    print(f"  Type:          {m.meeting_type or '-'}")
    print(f"  Staff:         {m.staff_name or '-'}")
    print(f"  Location:      {m.location or '-'}")
    print(f"  Status:        {m.status}")
    print(f"  Summary:       {m.summary or '-'}")
    print(f"  Notes:         {m.notes or '-'}")


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


def _collect_fields(existing: data.Meeting | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["meeting_date"] = ask("Date (YYYY-MM-DD)",
                                 existing.meeting_date if existing else None)
    fields["meeting_time"] = ask("Time (HH:MM)",
                                 existing.meeting_time if existing else None)
    fields["meeting_type"] = ask(f"Type ({'/'.join(MEETING_TYPES)})",
                                 existing.meeting_type if existing else None)
    fields["staff_id"]     = ask("Staff ID",
                                 existing.staff_id if existing else None)
    fields["location"]     = ask("Location",
                                 existing.location if existing else None)
    fields["status"]       = ask(f"Status ({'/'.join(STATUSES)})",
                                 existing.status if existing else "scheduled")
    fields["summary"]      = ask("Summary",
                                 existing.summary if existing else None)
    fields["notes"]        = ask("Notes",
                                 existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: parent_meetings open_manager")
    while True:
        print("\n  ── Parent Meetings ──")
        _print_table(data.list_meetings())
        print("\n   A) Add meeting    V) View    E) Edit    D) Delete")
        print("   C) Meetings for a child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            mid = _prompt("  Meeting ID: ")
            m = data.get_meeting(mid)
            if m is None:
                print("  No meeting with that ID.")
            else:
                _print_detail(m)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "c":
            pid = _prompt("  Child ID: ")
            _print_table(data.list_meetings(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Parent Meeting ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    m = data.create_meeting(fields)
    print(f"\n  Added parent meeting {m.meeting_id} for "
          f"{m.child_name or pid} on {m.meeting_date or '-'}.")


@_safe
def open_edit() -> None:
    mid = _prompt("  Meeting ID: ")
    if not mid:
        print("  Cancelled.")
        return
    existing = data.get_meeting(mid)
    if existing is None:
        print("  No meeting with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    m = data.update_meeting(mid, fields)
    print(f"\n  Updated parent meeting {m.meeting_id}.")


@_safe
def open_delete() -> None:
    mid = _prompt("  Meeting ID to delete: ")
    if not mid:
        print("  Cancelled.")
        return
    existing = data.get_meeting(mid)
    if existing is None:
        print("  No meeting with that ID.")
        return
    desc = (f"{existing.meeting_type or 'meeting'} for "
            f"{existing.child_name or existing.pupil_id}")
    if _prompt(f"  Delete {desc} ({mid})? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_meeting(mid):
        print(f"  Deleted meeting {mid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Parent Meetings": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching parent_meetings CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
