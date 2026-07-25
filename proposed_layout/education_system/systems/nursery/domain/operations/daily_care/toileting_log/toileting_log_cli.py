"""CLI flow for the Nappy / Toileting Log (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.operations.daily_care.toileting_log import (
    toileting_log as data,
)
from education_system.systems.nursery.domain.operations.daily_care.toileting_log.toileting_log import (
    TYPES,
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


def _print_table(rows: list[data.ToiletingRecord]) -> None:
    if not rows:
        print("  (no toileting-log records)")
        return
    print(f"  {'ID':<8} {'Date':<11} {'Time':<6} {'Child':<22} "
          f"{'Type':<16} {'Cream':<6} {'Staff'}")
    print(f"  {'-'*8} {'-'*11} {'-'*6} {'-'*22} {'-'*16} {'-'*6} {'-'*16}")
    for r in rows:
        cream = "yes" if r.cream_applied else "no"
        print(f"  {r.record_id:<8} {r.log_date:<11} {(r.log_time or '-'):<6} "
              f"{(r.child_name or '-')[:22]:<22} {r.type[:16]:<16} "
              f"{cream:<6} {(r.staff_name or '-')[:16]}")


def _print_detail(r: data.ToiletingRecord) -> None:
    print(f"\n  ── Toileting log {r.record_id} ──")
    print(f"  Child:         {r.child_name or '-'} ({r.pupil_id})")
    print(f"  Date:          {r.log_date}")
    print(f"  Time:          {r.log_time or '-'}")
    print(f"  Type:          {r.type}")
    print(f"  Cream applied: {'Yes' if r.cream_applied else 'No'}")
    print(f"  Staff:         {r.staff_name or '-'} ({r.staff_id or '-'})")
    print(f"  Notes:         {r.notes or '-'}")


def _pick(label: str, choices: list[tuple[str, str]]) -> str | None:
    if not choices:
        print(f"  (no {label} available)")
        return None
    print(f"  {label.capitalize()}:")
    for i, (_id, text) in enumerate(choices, 1):
        print(f"    {i}) {text}")
    raw = _prompt(f"  Select {label} (number, blank to skip): ")
    if not raw:
        return None
    try:
        idx = int(raw)
    except ValueError:
        print("  Invalid selection.")
        return None
    if 1 <= idx <= len(choices):
        return choices[idx - 1][0]
    print("  Invalid selection.")
    return None


def _pick_type(current: str | None = None) -> str:
    print("  Type:")
    for i, t in enumerate(TYPES, 1):
        print(f"    {i}) {t}")
    suffix = f" [{current}]" if current else ""
    raw = _prompt(f"  Select type (number){suffix}: ")
    if not raw:
        return current or "nappy - wet"
    try:
        idx = int(raw)
        if 1 <= idx <= len(TYPES):
            return TYPES[idx - 1]
    except ValueError:
        pass
    print("  Invalid selection — keeping default.")
    return current or "nappy - wet"


def _collect_fields(existing: data.ToiletingRecord | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    fields["log_date"] = ask("Date (YYYY-MM-DD, blank=today)",
                             existing.log_date if existing else None)
    fields["log_time"] = ask("Time (HH:MM)",
                             existing.log_time if existing else None)
    fields["type"] = _pick_type(existing.type if existing else None)
    cream_cur = ("y" if existing.cream_applied else "n") if existing else None
    fields["cream_applied"] = ask("Barrier cream applied? (y/n)", cream_cur)
    staff = _pick("staff", data.list_staff_choices())
    if staff is not None:
        fields["staff_id"] = staff
    elif existing is not None:
        fields["staff_id"] = existing.staff_id or ""
    fields["notes"] = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: toileting_log open_manager")
    date_filter = ""
    while True:
        scope = f"date {date_filter}" if date_filter else "all dates"
        print(f"\n  ── Nappy / Toileting Log ({scope}) ──")
        _print_table(data.list_records(log_date=date_filter or None))
        print("\n   A) Add    V) View    E) Edit    D) Delete")
        print("   F) Filter by date    C) Clear filter    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            rid = _prompt("  Record ID: ")
            r = data.get_record(rid)
            if r is None:
                print("  No record with that ID.")
            else:
                _print_detail(r)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "f":
            date_filter = _prompt("  Date (YYYY-MM-DD): ")
        elif choice == "c":
            date_filter = ""
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    logger.debug("CLI: toileting_log open_add")
    print("\n  ── Add Toileting-Log Record ──")
    pid = _pick("child", data.list_pupil_choices())
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields()
    fields["pupil_id"] = pid
    r = data.create_record(fields)
    print(f"\n  Created toileting-log record {r.record_id} for {r.child_name} "
          f"({r.type}).")


@_safe
def open_edit() -> None:
    logger.debug("CLI: toileting_log open_edit")
    rid = _prompt("  Record ID: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    r = data.update_record(rid, fields)
    print(f"\n  Updated toileting-log record {r.record_id}.")


@_safe
def open_delete() -> None:
    logger.debug("CLI: toileting_log open_delete")
    rid = _prompt("  Record ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    confirm = _prompt(
        f"  Delete toileting-log record {rid} for {existing.child_name}? (y/N): "
    ).lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_record(rid):
        print(f"  Deleted record {rid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Nappy / Toileting Log": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching toileting_log CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
