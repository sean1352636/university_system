"""CLI flow for Key Person Assignment (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.key_persons import (
    key_persons as data,
)
from education_system.nursery_system.modules.domain.key_persons.key_persons import (
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


def _print_table(rows: list[data.Assignment]) -> None:
    if not rows:
        print("  (no children on roll)")
        return
    print(f"  {'Pupil':<8} {'Name':<24} {'Room':<16} {'Key person'}")
    print(f"  {'-'*8} {'-'*24} {'-'*16} {'-'*24}")
    for a in rows:
        kp = a.key_person_name or ("— UNASSIGNED —" if not a.key_person else a.key_person)
        print(f"  {a.pupil_id:<8} {a.child_name[:24]:<24} "
              f"{(a.room or '-')[:16]:<16} {kp}")


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


@_safe
def open_manager() -> None:
    logger.debug("CLI: key_persons open_manager")
    while True:
        s = data.summary()
        print("\n  ── Key Person Assignment ──")
        print(f"  Active children: {s['total']}   Assigned: {s['assigned']}"
              f"   Unassigned: {s['unassigned']}")
        _print_table(data.list_assignments())
        print("\n   A) Assign / change key person    U) Show unassigned only")
        print("   C) Caseloads (per practitioner)    R) Bulk-assign a room    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_assign()
        elif choice == "u":
            rows = data.list_unassigned()
            print(f"\n  {len(rows)} child(ren) with no key person:")
            _print_table(rows)
            _prompt("  Press Enter to continue...")
        elif choice == "c":
            open_caseloads()
        elif choice == "r":
            open_bulk_assign()
        else:
            print("  Invalid selection.")


@_safe
def open_assign() -> None:
    logger.debug("CLI: key_persons open_assign")
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    existing = data.get_assignment(pid)
    if existing is None:
        print("  No active child with that ID.")
        return
    print(f"  {existing.child_name} (room {existing.room or '-'}) — current key "
          f"person: {existing.key_person_name or 'none'}")
    _show_staff()
    sid = _prompt("  Staff ID (blank to clear): ")
    a = data.assign(pid, sid or None)
    print(f"  Key person for {a.child_name} is now "
          f"{a.key_person_name or '(none)'}.")


@_safe
def open_bulk_assign() -> None:
    logger.debug("CLI: key_persons open_bulk_assign")
    room = _prompt("  Room name to bulk-assign: ")
    if not room:
        print("  Cancelled.")
        return
    _show_staff()
    sid = _prompt("  Staff ID for unassigned children in this room: ")
    if not sid:
        print("  Cancelled.")
        return
    n = data.assign_room(room, sid)
    print(f"  Assigned key person to {n} previously-unassigned child(ren) "
          f"in {room}.")


@_safe
def open_caseloads() -> None:
    logger.debug("CLI: key_persons open_caseloads")
    print("\n  ── Key Person Caseloads ──")
    for cl in data.list_caseloads():
        room = f" ({cl.room})" if cl.room else ""
        print(f"\n  {cl.staff_name}{room} — {cl.count} child(ren)")
        for a in cl.children:
            print(f"    {a.pupil_id:<8} {a.child_name} [{a.room or '-'}]")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Key Person Assignment": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching key_persons CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
