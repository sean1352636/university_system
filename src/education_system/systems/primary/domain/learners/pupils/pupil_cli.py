"""CLI handlers for pupil CRUD in the Primary School System."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.primary.domain.learners.pupils import pupils as data
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
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
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_table(rows: list[data.Pupil]) -> None:
    if not rows:
        print("  (no pupils)")
        return
    print(f"  {'ID':<10} {'Year':<4} {'Class':<8} {'Name':<28} {'Parent'}")
    print(f"  {'-'*10} {'-'*4} {'-'*8} {'-'*28} {'-'*20}")
    for p in rows:
        print(f"  {p.pupil_id:<10} {p.year_group:<4} "
              f"{(p.class_name or '-'):<8} {p.full_name[:28]:<28} "
              f"{p.parent_name or '-'}")


def _print_profile(p: data.Pupil) -> None:
    print(f"\n  ── Pupil {p.pupil_id} ──")
    print(f"  Name:           {p.full_name}")
    print(f"  Year group:     {p.year_group}")
    print(f"  Class:          {p.class_name or '-'}")
    print(f"  Date of birth:  {p.date_of_birth or '-'}")
    print(f"  Email:          {p.email}")
    print(f"  Parent:         {p.parent_name or '-'}")
    print(f"  Parent phone:   {p.parent_phone or '-'}")
    print(f"  Medical notes:  {p.medical_notes or '-'}")
    print(f"  SEND:           {p.send_status or '-'}")


def _collect_fields(existing: data.Pupil | None = None) -> dict[str, str]:
    def ask(label: str, current: str | None = None) -> str:
        suffix = f" [{current}]" if current else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (current or "")
    fields: dict[str, str] = {}
    fields["first_name"]    = ask("First name",
                                   existing.first_name if existing else None)
    fields["last_name"]     = ask("Last name",
                                   existing.last_name if existing else None)
    fields["year_group"]    = ask(
        f"Year group ({'/'.join(YEAR_GROUPS)})",
        existing.year_group if existing else None,
    )
    fields["class_name"]    = ask("Class",
                                   existing.class_name if existing else None)
    fields["date_of_birth"] = ask("Date of birth (YYYY-MM-DD)",
                                   existing.date_of_birth if existing else None)
    fields["parent_name"]   = ask("Parent name",
                                   existing.parent_name if existing else None)
    fields["parent_phone"]  = ask("Parent phone",
                                   existing.parent_phone if existing else None)
    fields["medical_notes"] = ask("Medical notes",
                                   existing.medical_notes if existing else None)
    fields["send_status"]   = ask("SEND (yes/no)",
                                   existing.send_status if existing else None)
    return fields


@_safe
def open_directory() -> None:
    logger.debug("CLI: open_directory")
    while True:
        print("\n  ── Pupil Directory ──")
        try:
            rows = data.list_pupils()
        except Exception as e:
            logger.exception("Failed to load pupil list")
            print(f"  Could not load pupil list: {e}")
            return
        _print_table(rows)
        print("\n   A) Add pupil   V) View pupil   E) Edit pupil   D) Delete pupil")
        print("   0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add_pupil()
        elif choice == "v":
            pid = _prompt("  Pupil ID: ")
            p = data.get_pupil(pid)
            if p is None:
                print("  No pupil with that ID.")
            else:
                _print_profile(p)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit_pupil()
        elif choice == "d":
            open_delete_pupil()
        else:
            print("  Invalid selection.")


@_safe
def open_add_pupil() -> None:
    logger.debug("CLI: open_add_pupil")
    print("\n  ── Add Pupil ──")
    fields = _collect_fields()
    p = data.create_pupil(fields)
    print(f"\n  Created pupil {p.pupil_id} ({p.full_name}, year {p.year_group})")
    print(f"  Auto-generated school email: {p.email}")


@_safe
def open_edit_pupil() -> None:
    logger.debug("CLI: open_edit_pupil")
    print("\n  ── Edit Pupil ──")
    pid = _prompt("  Pupil ID: ")
    if not pid:
        print("  Cancelled.")
        return
    existing = data.get_pupil(pid)
    if existing is None:
        print("  No pupil with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_fields(existing)
    p = data.update_pupil(pid, fields)
    print(f"\n  Updated pupil {p.pupil_id} ({p.full_name})")


@_safe
def open_delete_pupil() -> None:
    logger.debug("CLI: open_delete_pupil")
    print("\n  ── Delete Pupil ──")
    pid = _prompt("  Pupil ID: ")
    if not pid:
        print("  Cancelled.")
        return
    existing = data.get_pupil(pid)
    if existing is None:
        print("  No pupil with that ID.")
        return
    confirm = _prompt(f"  Delete {existing.full_name} ({pid})? (y/N): ").lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_pupil(pid):
        print(f"  Deleted pupil {pid}.")
    else:
        print("  Could not delete (already removed?).")


@_safe
def open_search() -> None:
    logger.debug("CLI: open_search")
    print("\n  ── Search Pupils ──")
    q = _prompt("  Search (id / name / class / email): ")
    rows = data.search_pupils(q)
    print(f"\n  {len(rows)} match(es):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def open_profile() -> None:
    logger.debug("CLI: open_profile")
    print("\n  ── Pupil Profile ──")
    pid = _prompt("  Pupil ID: ")
    if not pid:
        print("  Cancelled.")
        return
    p = data.get_pupil(pid)
    if p is None:
        print("  No pupil with that ID.")
    else:
        _print_profile(p)
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {
    "Pupil Directory": open_directory,
    "Add Pupil":       open_add_pupil,
    "Search Pupils":   open_search,
    "Pupil Profile":   open_profile,
}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching pupil CLI label: %s", label)
    handler()
    return True
