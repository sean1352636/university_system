"""CLI flow for Settling-In (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.admissions.settling_in import (
    settling_in as data,
)
from education_system.systems.nursery.domain.admissions.settling_in.settling_in import (
    RATINGS,
    SESSION_TYPES,
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


def _print_sessions(rows: list[data.SettlingSession]) -> None:
    if not rows:
        print("  (no settling-in sessions)")
        return
    print(f"  {'ID':<8} {'Child':<22} {'Date':<12} {'Type':<16} "
          f"{'Rating':<10} {'Key person'}")
    print(f"  {'-'*8} {'-'*22} {'-'*12} {'-'*16} {'-'*10} {'-'*16}")
    for s in rows:
        print(f"  {s.session_id:<8} {(s.child_name or '-')[:22]:<22} "
              f"{(s.session_date or '-'):<12} {(s.session_type or '-')[:16]:<16} "
              f"{(s.settled_rating or '-'):<10} {s.key_person_name or '-'}")


def _print_by_child(rows: list[data.ChildSettling]) -> None:
    print(f"  {'Pupil':<8} {'Name':<24} {'Room':<16} {'Sessions':<9} {'Latest rating'}")
    print(f"  {'-'*8} {'-'*24} {'-'*16} {'-'*9} {'-'*14}")
    for c in rows:
        print(f"  {c.pupil_id:<8} {c.child_name[:24]:<24} {(c.room or '-')[:16]:<16} "
              f"{c.session_count:<9} {c.latest_rating or '— none —'}")


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
        return
    if choices:
        print("  Staff: " + ", ".join(label for _id, label in choices))


def _collect_fields(existing: data.SettlingSession | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["session_date"]     = ask("Session date (YYYY-MM-DD)",
                                     existing.session_date if existing else None)
    fields["session_type"]     = ask(f"Type ({'/'.join(SESSION_TYPES)})",
                                     existing.session_type if existing else None)
    fields["duration_minutes"] = ask("Duration (minutes)",
                                     existing.duration_minutes if existing else None)
    _show_staff()
    fields["key_person"]       = ask("Key person (staff ID)",
                                     existing.key_person if existing else None)
    fields["settled_rating"]   = ask(f"Settled rating ({'/'.join(RATINGS)})",
                                     existing.settled_rating if existing else None)
    fields["notes"]            = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: settling_in open_manager")
    while True:
        print("\n  ── Settling-In ──")
        print("  Children (latest settling status):")
        _print_by_child(data.list_by_child())
        print("\n  Recent sessions:")
        _print_sessions(data.list_sessions())
        print("\n   A) Add session    V) View    E) Edit    D) Delete")
        print("   C) Sessions for a child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            sid = _prompt("  Session ID: ")
            s = data.get_session(sid)
            if s is None:
                print("  No session with that ID.")
            else:
                _print_detail(s)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "c":
            pid = _prompt("  Child ID: ")
            _print_sessions(data.list_sessions(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


def _print_detail(s: data.SettlingSession) -> None:
    print(f"\n  ── Settling-in session {s.session_id} ──")
    print(f"  Child:        {s.child_name or '-'} ({s.pupil_id})")
    print(f"  Date:         {s.session_date or '-'}")
    print(f"  Type:         {s.session_type or '-'}")
    print(f"  Duration:     {s.duration_minutes or '-'} min")
    print(f"  Key person:   {s.key_person_name or s.key_person or '-'}")
    print(f"  Settled:      {s.settled_rating or '-'}")
    print(f"  Notes:        {s.notes or '-'}")


@_safe
def open_add() -> None:
    print("\n  ── Add Settling-In Session ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    s = data.create_session(fields)
    print(f"\n  Logged settling-in session {s.session_id} for {s.child_name}.")


@_safe
def open_edit() -> None:
    sid = _prompt("  Session ID: ")
    if not sid:
        print("  Cancelled.")
        return
    existing = data.get_session(sid)
    if existing is None:
        print("  No session with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    s = data.update_session(sid, fields)
    print(f"\n  Updated settling-in session {s.session_id}.")


@_safe
def open_delete() -> None:
    sid = _prompt("  Session ID to delete: ")
    if not sid:
        print("  Cancelled.")
        return
    if data.get_session(sid) is None:
        print("  No session with that ID.")
        return
    if _prompt(f"  Delete session {sid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_session(sid):
        print(f"  Deleted session {sid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Settling-In": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching settling_in CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
