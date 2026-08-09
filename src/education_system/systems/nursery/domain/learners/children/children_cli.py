"""CLI flow for Child Directory (Nursery System).

Provides the interactive screens behind the four "Children & Admissions"
menu labels handled here — Child Directory, Add Child, Search Children and
Child Profile — and a :func:`dispatch` hook the launcher calls for each
selected label.

Every handler is wrapped by :func:`_safe` so a domain or DB error is logged
and reported without tearing down the surrounding menu loop.
"""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.learners.children import children as data
from education_system.systems.nursery.domain.learners.children import primary_transfer
from education_system.systems.nursery.domain.learners.children.children import (
    FUNDED_HOURS_OPTIONS,
    ROOMS,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    """Catch unexpected errors in a CLI handler — log and keep the menu alive."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:  # noqa: BLE001 - last-resort guard for the menu
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_table(rows: list[data.Child]) -> None:
    if not rows:
        print("  (no children on roll)")
        return
    print(f"  {'ID':<8} {'Name':<26} {'Room':<16} {'Funded':<20} {'Key person'}")
    print(f"  {'-'*8} {'-'*26} {'-'*16} {'-'*20} {'-'*20}")
    for c in rows:
        print(f"  {c.pupil_id:<8} {c.full_name[:26]:<26} "
              f"{(c.room or '-')[:16]:<16} {(c.funded_hours or '-')[:20]:<20} "
              f"{c.key_person_name or '-'}")


def _print_profile(c: data.Child) -> None:
    print(f"\n  ── Child {c.pupil_id} ──")
    print(f"  Name:           {c.full_name}")
    print(f"  Date of birth:  {c.date_of_birth or '-'}")
    print(f"  Room:           {c.room or '-'}")
    print(f"  Key person:     {c.key_person_name or c.key_person or '-'}")
    print(f"  Funded hours:   {c.funded_hours or '-'}")
    print(f"  Start date:     {c.start_date or '-'}")
    print(f"  Status:         {c.status}")
    print(f"  Parent:         {c.parent_name or '-'}")
    print(f"  Parent phone:   {c.parent_phone or '-'}")
    print(f"  Parent email:   {c.parent_email or '-'}")
    print(f"  Allergies:      {c.allergies or '-'}")
    print(f"  Medical notes:  {c.medical_notes or '-'}")


def _show_key_people() -> None:
    try:
        choices = data.list_key_person_choices()
    except Exception:
        logger.exception("Could not load key-person choices")
        return
    if choices:
        print("  Key people (staff): "
              + ", ".join(label for _id, label in choices))


def _collect_fields(existing: data.Child | None = None) -> dict[str, str]:
    def ask(label: str, current: str | None = None) -> str:
        suffix = f" [{current}]" if current else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (current or "")

    fields: dict[str, str] = {}
    fields["first_name"]    = ask("First name",
                                   existing.first_name if existing else None)
    fields["last_name"]     = ask("Last name",
                                   existing.last_name if existing else None)
    fields["date_of_birth"] = ask("Date of birth (YYYY-MM-DD)",
                                   existing.date_of_birth if existing else None)
    fields["room"]          = ask(f"Room ({'/'.join(ROOMS)})",
                                   existing.room if existing else None)
    _show_key_people()
    fields["key_person"]    = ask("Key person (staff ID)",
                                   existing.key_person if existing else None)
    funded = [o for o in FUNDED_HOURS_OPTIONS if o]
    fields["funded_hours"]  = ask(f"Funded hours ({'/'.join(funded)})",
                                   existing.funded_hours if existing else None)
    fields["start_date"]    = ask("Start date (YYYY-MM-DD)",
                                   existing.start_date if existing else None)
    fields["parent_name"]   = ask("Parent / carer name",
                                   existing.parent_name if existing else None)
    fields["parent_phone"]  = ask("Parent phone",
                                   existing.parent_phone if existing else None)
    fields["parent_email"]  = ask("Parent email",
                                   existing.parent_email if existing else None)
    fields["allergies"]     = ask("Allergies",
                                   existing.allergies if existing else None)
    fields["medical_notes"] = ask("Medical notes",
                                   existing.medical_notes if existing else None)
    if existing is not None:
        fields["status"] = ask(f"Status ({'/'.join(data.STATUSES)})",
                               existing.status)
    return fields


@_safe
def open_directory() -> None:
    logger.debug("CLI: open_directory")
    show_left = False
    while True:
        scope = "all (incl. leavers)" if show_left else "active"
        print(f"\n  ── Child Directory ({scope}) ──")
        try:
            rows = data.list_children(include_left=show_left)
        except Exception as e:  # noqa: BLE001
            logger.exception("Failed to load child list")
            print(f"  Could not load child list: {e}")
            return
        _print_table(rows)
        print("\n   A) Add child    V) View child    E) Edit child")
        print("   D) Delete child    T) Toggle leavers    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add_child()
        elif choice == "v":
            cid = _prompt("  Child ID: ")
            c = data.get_child(cid)
            if c is None:
                print("  No child with that ID.")
            else:
                _print_profile(c)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit_child()
        elif choice == "d":
            open_delete_child()
        elif choice == "t":
            show_left = not show_left
        else:
            print("  Invalid selection.")


@_safe
def open_add_child() -> None:
    logger.debug("CLI: open_add_child")
    print("\n  ── Add Child ──")
    fields = _collect_fields()
    c = data.create_child(fields)
    print(f"\n  Created child {c.pupil_id} ({c.full_name}, room {c.room or '-'}).")


@_safe
def open_edit_child() -> None:
    logger.debug("CLI: open_edit_child")
    print("\n  ── Edit Child ──")
    cid = _prompt("  Child ID: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_child(cid)
    if existing is None:
        print("  No child with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    c = data.update_child(cid, fields)
    print(f"\n  Updated child {c.pupil_id} ({c.full_name}).")


@_safe
def open_delete_child() -> None:
    logger.debug("CLI: open_delete_child")
    print("\n  ── Delete Child ──")
    cid = _prompt("  Child ID: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_child(cid)
    if existing is None:
        print("  No child with that ID.")
        return
    print("  Tip: to keep the record but take the child off roll, edit and set "
          "status to 'left' instead.")
    confirm = _prompt(
        f"  Permanently delete {existing.full_name} ({cid})? (y/N): ").lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_child(cid):
        print(f"  Deleted child {cid}.")
    else:
        print("  Could not delete (already removed?).")


@_safe
def open_search() -> None:
    logger.debug("CLI: open_search")
    print("\n  ── Search Children ──")
    q = _prompt("  Search (id / name / room / parent / email): ")
    rows = data.search_children(q)
    print(f"\n  {len(rows)} match(es):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def open_profile() -> None:
    logger.debug("CLI: open_profile")
    print("\n  ── Child Profile ──")
    cid = _prompt("  Child ID: ")
    if not cid:
        print("  Cancelled.")
        return
    c = data.get_child(cid)
    if c is None:
        print("  No child with that ID.")
    else:
        _print_profile(c)
    _prompt("\n  Press Enter to continue...")


@_safe
def open_move_to_primary() -> None:
    """Move a child onto the primary school roll."""
    logger.debug("CLI: open_move_to_primary")
    print("\n  ── Move to Primary School ──")
    cid = _prompt("  Child ID: ")
    if not cid:
        print("  Cancelled.")
        return
    c = data.get_child(cid)
    if c is None:
        print("  No child with that ID.")
        return
    if c.status == "left":
        print(f"  {c.full_name} ({cid}) has already left the nursery.")
        return
    groups = ", ".join(primary_transfer.primary_year_groups())
    year = _prompt(
        f"  Primary year group [{primary_transfer.DEFAULT_YEAR_GROUP}] "
        f"(one of {groups}): ") or primary_transfer.DEFAULT_YEAR_GROUP
    class_name = _prompt("  Class (optional): ")
    confirm = _prompt(
        f"  Create a primary pupil for {c.full_name} and take them off the "
        f"nursery roll? (y/N): ").lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    result = primary_transfer.move_to_primary_school(
        cid, year_group=year, class_name=class_name or None)
    print(f"  Moved {result.source_child_id} to primary pupil "
          f"{result.primary_pupil_id} (year {result.year_group}).")
    print(f"  School email: {result.primary_email}")
    _prompt("\n  Press Enter to continue...")


# Maps the launcher menu labels (from ``menu.py``) to the handler above.
_DISPATCH = {
    "Child Directory":        open_directory,
    "Add Child":              open_add_child,
    "Search Children":        open_search,
    "Child Profile":          open_profile,
    "Move to Primary School": open_move_to_primary,
}


def dispatch(label: str) -> bool:
    """Run the handler for ``label`` if this module owns it; else return False."""
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching child CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    """Backwards-compatible entry point — opens the directory screen."""
    open_directory()
