"""CLI flow for Learning Journeys (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.learning_journeys import (
    learning_journeys as data,
)
from education_system.nursery_system.modules.domain.learning_journeys.learning_journeys import (
    AREAS,
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
    return "Yes" if flag else "No"


def _print_table(rows: list[data.JourneyEntry]) -> None:
    if not rows:
        print("  (no learning journey entries)")
        return
    print(f"  {'ID':<8} {'Child':<20} {'Date':<12} {'Title':<28} "
          f"{'Area':<16} {'Wow':<4} {'Shared'}")
    print(f"  {'-'*8} {'-'*20} {'-'*12} {'-'*28} {'-'*16} {'-'*4} {'-'*6}")
    for e in rows:
        area_short = (e.area or "-")[:16]
        print(f"  {e.entry_id:<8} {(e.child_name or '-')[:20]:<20} "
              f"{(e.entry_date or '-')[:12]:<12} {e.title[:28]:<28} "
              f"{area_short:<16} {'★' if e.wow_moment else '':<4} "
              f"{'Yes' if e.shared_with_parent else ''}")


def _print_detail(e: data.JourneyEntry) -> None:
    print(f"\n  ── Learning Journey {e.entry_id} ──")
    print(f"  Child:              {e.child_name or '-'} ({e.pupil_id})")
    print(f"  Date:               {e.entry_date or '-'}")
    print(f"  Title:              {e.title}")
    print(f"  Area:               {e.area or '-'}")
    print(f"  Description:        {e.description or '-'}")
    print(f"  Wow moment:         {_yn(e.wow_moment)}")
    print(f"  Shared with parent: {_yn(e.shared_with_parent)}")
    print(f"  Staff:              {e.staff_name or (e.staff_id or '-')}")
    print(f"  Notes:              {e.notes or '-'}")


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


def _collect_fields(existing: data.JourneyEntry | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["title"]       = ask("Title", existing.title if existing else None)
    fields["entry_date"]  = ask("Date (YYYY-MM-DD)",
                                existing.entry_date if existing else None)
    fields["area"]        = ask(
        f"Area ({'/'.join(a[:4] for a in AREAS)}) — leave blank for none",
        existing.area if existing else None)
    fields["description"] = ask("Description", existing.description if existing else None)
    fields["wow_moment"]  = _ask_bool("Wow moment?",
                                      existing.wow_moment if existing else False)
    fields["shared_with_parent"] = _ask_bool(
        "Shared with parent?",
        existing.shared_with_parent if existing else False)
    _show_staff()
    fields["staff_id"]    = ask("Staff ID (leave blank for none)",
                                existing.staff_id if existing else None)
    fields["notes"]       = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: learning_journeys open_manager")
    while True:
        print("\n  ── Learning Journeys ──")
        _print_table(data.list_entries())
        print("\n   A) Add entry    V) View    E) Edit    D) Delete")
        print("   F) Filter by child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            eid = _prompt("  Entry ID: ")
            e = data.get_entry(eid)
            if e is None:
                print("  No entry with that ID.")
            else:
                _print_detail(e)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "f":
            pid = _prompt("  Child ID: ")
            _print_table(data.list_entries(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Learning Journey Entry ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    e = data.create_entry(fields)
    print(f"\n  Added learning journey {e.entry_id} ({e.title}) for "
          f"{e.child_name or pid}.")


@_safe
def open_edit() -> None:
    eid = _prompt("  Entry ID: ")
    if not eid:
        print("  Cancelled.")
        return
    existing = data.get_entry(eid)
    if existing is None:
        print("  No entry with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    e = data.update_entry(eid, fields)
    print(f"\n  Updated learning journey {e.entry_id}.")


@_safe
def open_delete() -> None:
    eid = _prompt("  Entry ID to delete: ")
    if not eid:
        print("  Cancelled.")
        return
    existing = data.get_entry(eid)
    if existing is None:
        print("  No entry with that ID.")
        return
    if _prompt(f"  Delete '{existing.title}' ({eid})? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_entry(eid):
        print(f"  Deleted entry {eid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Learning Journeys": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching learning_journeys CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
