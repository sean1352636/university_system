"""CLI flow for Sleep Log (Nursery System)."""

from __future__ import annotations

import datetime as _dt
import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.sleep_log import sleep_log as data
from education_system.nursery_system.modules.domain.sleep_log.sleep_log import (
    LOCATIONS,
    ValidationError,
    _minutes_between,
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


def _fmt_duration(minutes: int | None) -> str:
    if minutes is None:
        return "-"
    h, m = divmod(minutes, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m"


def _print_table(rows: list[data.SleepRecord]) -> None:
    if not rows:
        print("  (no sleep records)")
        return
    print(f"  {'ID':<8} {'Date':<11} {'Child':<20} {'Start':<6} {'End':<6} "
          f"{'Dur':<7} {'Location':<10} {'Chk'}")
    print(f"  {'-'*8} {'-'*11} {'-'*20} {'-'*6} {'-'*6} {'-'*7} {'-'*10} {'-'*3}")
    for r in rows:
        print(f"  {r.sleep_id:<8} {r.sleep_date:<11} "
              f"{(r.child_name or '-')[:20]:<20} {(r.start_time or '-'):<6} "
              f"{(r.end_time or '-'):<6} {_fmt_duration(r.duration_minutes):<7} "
              f"{(r.location or '-')[:10]:<10} {r.checks}")


def _print_detail(r: data.SleepRecord) -> None:
    print(f"\n  ── Sleep record {r.sleep_id} ──")
    print(f"  Child:        {r.child_name or '-'} ({r.pupil_id})")
    print(f"  Date:         {r.sleep_date}")
    print(f"  Start → End:  {r.start_time or '-'} → {r.end_time or '-'}")
    print(f"  Duration:     {_fmt_duration(r.duration_minutes)}")
    print(f"  Location:     {r.location or '-'}")
    print(f"  Checks:       {r.checks}")
    print(f"  Staff:        {r.staff_name or '-'}"
          + (f" ({r.staff_id})" if r.staff_id else ""))
    print(f"  Notes:        {r.notes or '-'}")


def _pick(prompt: str, choices: list[tuple[str, str]]) -> str | None:
    if not choices:
        print(f"  (no options available for {prompt})")
        return None
    print(f"  {prompt}:")
    for i, (_id, label) in enumerate(choices, 1):
        print(f"    {i}) {label}")
    raw = _prompt("  Select number (blank to skip): ")
    if not raw:
        return None
    try:
        idx = int(raw)
    except ValueError:
        print("  Not a number — skipped.")
        return None
    if 1 <= idx <= len(choices):
        return choices[idx - 1][0]
    print("  Out of range — skipped.")
    return None


def _pick_location() -> str:
    print("  Location:")
    for i, loc in enumerate(LOCATIONS, 1):
        print(f"    {i}) {loc}")
    raw = _prompt("  Select number or type a value (blank to skip): ")
    if not raw:
        return ""
    try:
        idx = int(raw)
        if 1 <= idx <= len(LOCATIONS):
            return LOCATIONS[idx - 1]
    except ValueError:
        return raw
    return raw


def _collect_fields(existing: data.SleepRecord | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    today = _dt.date.today().isoformat()
    fields["sleep_date"] = ask("Sleep date (YYYY-MM-DD)",
                               existing.sleep_date if existing else today)
    fields["start_time"] = ask("Start time (HH:MM)",
                               existing.start_time if existing else None)
    fields["end_time"] = ask("End time (HH:MM)",
                             existing.end_time if existing else None)
    if existing is None and fields["start_time"] and fields["end_time"]:
        try:
            mins = _minutes_between(fields["start_time"], fields["end_time"])
            print(f"  → Computed duration: {mins} minutes")
        except (ValueError, AttributeError):
            pass
    if existing is not None:
        fields["duration_minutes"] = ask("Duration (minutes)",
                                         existing.duration_minutes)
    loc = _pick_location()
    fields["location"] = loc if loc else (existing.location if existing else "")
    fields["checks"] = ask("Sleep checks carried out",
                           existing.checks if existing else 0)
    staff_id = _pick("Supervising staff", data.list_staff_choices())
    if staff_id:
        fields["staff_id"] = staff_id
    elif existing is not None:
        fields["staff_id"] = existing.staff_id or ""
    fields["notes"] = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: sleep_log open_manager")
    date_filter = ""
    while True:
        scope = f"date {date_filter}" if date_filter else "all dates"
        print(f"\n  ── Sleep Log ({scope}) ──")
        if date_filter:
            s = data.summary(date_filter)
            print(f"  Naps: {s['naps']}   "
                  f"Total slept: {_fmt_duration(s['total_minutes'])}")
        _print_table(data.list_records(sleep_date=date_filter or None))
        print("\n   L) Filter by date    A) Add    V) View    E) Edit")
        print("   D) Delete    C) Clear filter    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "l":
            date_filter = _prompt("  Date (YYYY-MM-DD): ")
        elif choice == "c":
            date_filter = ""
        elif choice == "a":
            open_add()
        elif choice == "v":
            sid = _prompt("  Record ID: ")
            r = data.get_record(sid)
            if r is None:
                print("  No record with that ID.")
            else:
                _print_detail(r)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    logger.debug("CLI: sleep_log open_add")
    print("\n  ── Add Sleep Record ──")
    pid = _pick("Child", data.list_pupil_choices())
    if not pid:
        print("  Cancelled — no child selected.")
        return
    fields = _collect_fields()
    fields["pupil_id"] = pid
    r = data.create_record(fields)
    print(f"\n  Created sleep record {r.sleep_id} for {r.child_name} "
          f"({_fmt_duration(r.duration_minutes)}).")


@_safe
def open_edit() -> None:
    logger.debug("CLI: sleep_log open_edit")
    sid = _prompt("  Record ID: ")
    if not sid:
        print("  Cancelled.")
        return
    existing = data.get_record(sid)
    if existing is None:
        print("  No record with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    r = data.update_record(sid, fields)
    print(f"\n  Updated sleep record {r.sleep_id}.")


@_safe
def open_delete() -> None:
    logger.debug("CLI: sleep_log open_delete")
    sid = _prompt("  Record ID to delete: ")
    if not sid:
        print("  Cancelled.")
        return
    existing = data.get_record(sid)
    if existing is None:
        print("  No record with that ID.")
        return
    confirm = _prompt(
        f"  Delete sleep record {sid} for {existing.child_name}? (y/N): "
    ).lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_record(sid):
        print(f"  Deleted record {sid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Sleep Log": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching sleep_log CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
