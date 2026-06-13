"""CLI flow for Qualifications & Training (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.qualifications import (
    qualifications as data,
)
from education_system.nursery_system.modules.domain.qualifications.qualifications import (
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


def _print_table(rows: list[data.TrainingRecord]) -> None:
    if not rows:
        print("  (no training records)")
        return
    print(f"  {'ID':<8} {'Staff':<22} {'Course':<26} {'Expiry':<12} {'State'}")
    print(f"  {'-'*8} {'-'*22} {'-'*26} {'-'*12} {'-'*10}")
    for r in rows:
        print(f"  {r.record_id:<8} {(r.staff_name or '-')[:22]:<22} "
              f"{r.course[:26]:<26} {(r.expiry_date or '-'):<12} {r.expiry_status}")


def _print_detail(r: data.TrainingRecord) -> None:
    print(f"\n  ── Training {r.record_id} ──")
    print(f"  Staff:          {r.staff_name or '-'} ({r.staff_id})")
    print(f"  Course:         {r.course}")
    print(f"  Level:          {r.level or '-'}")
    print(f"  Awarding body:  {r.awarding_body or '-'}")
    print(f"  Completed:      {r.completed_date or '-'}")
    print(f"  Expiry:         {r.expiry_date or '-'}  ({r.expiry_status})")
    print(f"  Certificate:    {r.certificate_ref or '-'}")
    print(f"  Status:         {r.status}")
    print(f"  Notes:          {r.notes or '-'}")


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


def _collect_fields(existing: data.TrainingRecord | None = None,
                    *, staff_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if staff_id is not None:
        fields["staff_id"] = staff_id
    fields["course"]          = ask("Course / qualification",
                                    existing.course if existing else None)
    fields["level"]           = ask("Level (e.g. Level 3)",
                                    existing.level if existing else None)
    fields["awarding_body"]   = ask("Awarding body",
                                    existing.awarding_body if existing else None)
    fields["completed_date"]  = ask("Completed date (YYYY-MM-DD)",
                                    existing.completed_date if existing else None)
    fields["expiry_date"]     = ask("Expiry date (YYYY-MM-DD, blank if none)",
                                    existing.expiry_date if existing else None)
    fields["certificate_ref"] = ask("Certificate reference",
                                    existing.certificate_ref if existing else None)
    fields["status"]          = ask(f"Status ({'/'.join(STATUSES)})",
                                    existing.status if existing else "valid")
    fields["notes"]           = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: qualifications open_manager")
    while True:
        s = data.summary()
        print("\n  ── Qualifications & Training ──")
        print(f"  Records: {s['total']}   Valid: {s['valid']}   "
              f"Expiring: {s['expiring']}   Expired: {s['expired']}   "
              f"In progress: {s['in_progress']}")
        _print_table(data.list_records())
        print("\n   A) Add    V) View    E) Edit    D) Delete")
        print("   X) Expiring / expired    C) For a staff member    0) Back")
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
        elif choice == "x":
            rows = data.list_expiring()
            print(f"\n  {len(rows)} expiring / expired:")
            _print_table(rows)
            _prompt("  Press Enter to continue...")
        elif choice == "c":
            sid = _prompt("  Staff ID: ")
            _print_table(data.list_records(staff_id=sid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Training Record ──")
    _show_staff()
    sid = _prompt("  Staff ID: ")
    if not sid:
        print("  Cancelled.")
        return
    fields = _collect_fields(staff_id=sid)
    r = data.create_record(fields)
    print(f"\n  Added training '{r.course}' for {r.staff_name} ({r.record_id}).")


@_safe
def open_edit() -> None:
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
    print(f"\n  Updated training record {r.record_id}.")


@_safe
def open_delete() -> None:
    rid = _prompt("  Record ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    if data.get_record(rid) is None:
        print("  No record with that ID.")
        return
    if _prompt(f"  Delete training record {rid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_record(rid):
        print(f"  Deleted record {rid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Qualifications & Training": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching qualifications CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
