"""CLI flow for the Existing Injuries Log (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.pastoral.health.existing_injuries import (
    existing_injuries as data,
)
from education_system.systems.nursery.domain.pastoral.health.existing_injuries.existing_injuries import (
    FEATURE_NAME,
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


def _yn(value: int) -> str:
    return "Yes" if value else "No"


def _print_table(rows: list[data.ExistingInjury]) -> None:
    if not rows:
        print("  (no existing-injury records)")
        return
    print(f"  {'ID':<8} {'Date':<11} {'Child':<22} {'Body part':<14} "
          f"{'Informed':<9} {'Signed'}")
    print(f"  {'-'*8} {'-'*11} {'-'*22} {'-'*14} {'-'*9} {'-'*6}")
    for r in rows:
        print(f"  {r.record_id:<8} {r.observed_date:<11} "
              f"{(r.child_name or '-')[:22]:<22} "
              f"{(r.body_part or '-')[:14]:<14} "
              f"{_yn(r.parent_informed):<9} {_yn(r.parent_signed)}")


def _print_detail(r: data.ExistingInjury) -> None:
    print(f"\n  ── Existing injury {r.record_id} ──")
    print(f"  Child:           {r.child_name or '-'} ({r.pupil_id})")
    print(f"  Observed:        {r.observed_date} {r.observed_time or ''}".rstrip())
    print(f"  Body part:       {r.body_part or '-'}")
    print(f"  Description:     {r.description or '-'}")
    print(f"  Explanation:     {r.explanation or '-'}")
    obs = r.observed_by_name or r.observed_by or "-"
    print(f"  Observed by:     {obs}")
    print(f"  Parent informed: {_yn(r.parent_informed)}")
    print(f"  Parent signed:   {_yn(r.parent_signed)}")
    print(f"  Notes:           {r.notes or '-'}")


def _pick_child() -> str | None:
    try:
        choices = data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        choices = []
    if choices:
        print("  Children:")
        for sid, label in choices:
            print(f"    {sid}  {label}")
    return _prompt("  Child ID: ") or None


def _pick_staff(current: str | None = None) -> str:
    try:
        choices = data.list_staff_choices()
    except Exception:
        logger.exception("Could not load staff choices")
        choices = []
    if choices:
        print("  Staff:")
        for sid, label in choices:
            print(f"    {sid}  {label}")
    cur = current or ""
    suffix = f" [{cur}]" if cur else ""
    v = _prompt(f"  Observed by (staff ID, blank=none){suffix}: ")
    return v if v else cur


def _collect_fields(existing: data.ExistingInjury | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    fields["observed_date"] = ask("Observed date (YYYY-MM-DD, blank=today)",
                                  existing.observed_date if existing else None)
    fields["observed_time"] = ask("Observed time (HH:MM)",
                                  existing.observed_time if existing else None)
    fields["body_part"] = ask("Body part",
                              existing.body_part if existing else None)
    fields["description"] = ask("Description",
                                existing.description if existing else None)
    fields["explanation"] = ask("Parent's explanation",
                                existing.explanation if existing else None)
    fields["observed_by"] = _pick_staff(existing.observed_by if existing else None)
    informed_cur = ("y" if existing.parent_informed else "n") if existing else "y"
    fields["parent_informed"] = ask("Parent informed? (y/n)", informed_cur)
    signed_cur = ("y" if existing.parent_signed else "n") if existing else "n"
    fields["parent_signed"] = ask("Parent signed? (y/n)", signed_cur)
    fields["notes"] = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: existing_injuries open_manager")
    date_filter: str | None = None
    while True:
        scope = f"date={date_filter}" if date_filter else "all dates"
        print(f"\n  ── {FEATURE_NAME} ({scope}) ──")
        _print_table(data.list_records(observed_date=date_filter))
        print("\n   L) List by date    A) Add    V) View    E) Edit")
        print("   D) Delete    C) Clear date filter    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "l":
            d = _prompt("  Date (YYYY-MM-DD, blank=all): ")
            date_filter = d or None
        elif choice == "c":
            date_filter = None
        elif choice == "a":
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
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    logger.debug("CLI: existing_injuries open_add")
    print("\n  ── Add Existing-Injury Record ──")
    pid = _pick_child()
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields()
    fields["pupil_id"] = pid
    r = data.create_record(fields)
    print(f"\n  Created existing-injury record {r.record_id} for {r.child_name}.")


@_safe
def open_edit() -> None:
    logger.debug("CLI: existing_injuries open_edit")
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
    print(f"\n  Updated existing-injury record {r.record_id}.")


@_safe
def open_delete() -> None:
    logger.debug("CLI: existing_injuries open_delete")
    rid = _prompt("  Record ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    confirm = _prompt(
        f"  Delete existing-injury record {rid} for {existing.child_name}? (y/N): "
    ).lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_record(rid):
        print(f"  Deleted record {rid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {FEATURE_NAME: open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching existing_injuries CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
