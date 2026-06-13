"""CLI flow for Sign In / Sign Out (Nursery System)."""

from __future__ import annotations

import datetime as _dt
import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.sign_in_out import (
    sign_in_out as data,
)
from education_system.nursery_system.modules.domain.sign_in_out.sign_in_out import (
    ValidationError,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _today() -> str:
    return _dt.date.today().isoformat()


def _now() -> str:
    return _dt.datetime.now().strftime("%H:%M")


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


def _print_table(rows: list[data.SignEvent]) -> None:
    if not rows:
        print("  (no sign in / out events)")
        return
    print(f"  {'ID':<8} {'Time':<6} {'Child':<22} {'Dir':<4} "
          f"{'Person':<18} {'Relationship':<14} {'Recorded by'}")
    print(f"  {'-'*8} {'-'*6} {'-'*22} {'-'*4} {'-'*18} {'-'*14} {'-'*12}")
    for r in rows:
        print(f"  {r.event_id:<8} {(r.event_time or '-'):<6} "
              f"{(r.child_name or '-')[:22]:<22} {r.direction:<4} "
              f"{(r.person_name or '-')[:18]:<18} "
              f"{(r.relationship or '-')[:14]:<14} {r.recorded_by_name or '-'}")


def _pick(choices: list[tuple[str, str]], what: str) -> str | None:
    if not choices:
        print(f"  No {what} available.")
        return None
    for i, (_id, label) in enumerate(choices, 1):
        print(f"    {i}) {label}")
    raw = _prompt(f"  Select {what} (number): ")
    if not raw:
        return None
    try:
        idx = int(raw)
    except ValueError:
        print("  Invalid selection.")
        return None
    if not 1 <= idx <= len(choices):
        print("  Invalid selection.")
        return None
    return choices[idx - 1][0]


@_safe
def _list_events() -> None:
    date = _prompt(f"  Date (YYYY-MM-DD) [{_today()}]: ") or _today()
    print(f"\n  ── Sign In / Sign Out — {date} ──")
    _print_table(data.list_events(event_date=date))


@_safe
def _sign(direction: str) -> None:
    verb = "IN" if direction == "in" else "OUT"
    print(f"\n  ── Sign a child {verb} ──")
    pid = _pick(data.list_pupil_choices(), "child")
    if not pid:
        print("  Cancelled.")
        return
    person = _prompt("  Person name (who is dropping off / collecting): ")
    relationship = _prompt("  Relationship to child: ")
    time = _prompt(f"  Time (HH:MM) [{_now()}]: ") or _now()
    print("  Recorded by (optional):")
    recorded_by = _pick(data.list_staff_choices(), "staff") or ""
    notes = _prompt("  Notes (optional): ")
    r = data.create_event({
        "pupil_id": pid, "direction": direction, "event_time": time,
        "person_name": person, "relationship": relationship,
        "recorded_by": recorded_by, "notes": notes,
    })
    print(f"\n  Signed {r.child_name} {verb} at {r.event_time or '-'} "
          f"(event {r.event_id}).")


@_safe
def _currently_in() -> None:
    date = _prompt(f"  Date (YYYY-MM-DD) [{_today()}]: ") or _today()
    rows = data.currently_in(date)
    print(f"\n  ── Currently in — {date} ({len(rows)}) ──")
    if not rows:
        print("  (no children currently signed in)")
        return
    for r in rows:
        print(f"    {r.child_name or r.pupil_id:<24} in at "
              f"{r.event_time or '-'}  ({r.person_name or '-'})")


@_safe
def _delete_event() -> None:
    eid = _prompt("  Event ID to delete: ")
    if not eid:
        print("  Cancelled.")
        return
    existing = data.get_event(eid)
    if existing is None:
        print("  No event with that ID.")
        return
    confirm = _prompt(
        f"  Delete event {eid} ({existing.direction} — "
        f"{existing.child_name})? (y/N): ").lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_event(eid):
        print(f"  Deleted event {eid}.")
    else:
        print("  Could not delete (already removed?).")


@_safe
def open_manager() -> None:
    logger.debug("CLI: sign_in_out open_manager")
    while True:
        print("\n  ── Sign In / Sign Out ──")
        print("   1) List events")
        print("   2) Sign a child IN")
        print("   3) Sign a child OUT")
        print("   4) Who's currently in")
        print("   5) Delete event")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        if choice == "1":
            _list_events()
        elif choice == "2":
            _sign("in")
        elif choice == "3":
            _sign("out")
        elif choice == "4":
            _currently_in()
        elif choice == "5":
            _delete_event()
        else:
            print("  Invalid selection.")


_DISPATCH = {"Sign In / Sign Out": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching sign_in_out CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
