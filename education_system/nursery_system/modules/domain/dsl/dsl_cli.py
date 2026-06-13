"""CLI flow for Designated Safeguarding Lead (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.dsl import dsl as data
from education_system.nursery_system.modules.domain.dsl.dsl import (
    DSL_ROLES,
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


def _print_table(rows: list[data.DSLRecord]) -> None:
    if not rows:
        print("  (no DSLs registered)")
        return
    print(f"  {'ID':<8} {'Staff':<24} {'Role':<14} {'Training expiry':<16} {'State'}")
    print(f"  {'-'*8} {'-'*24} {'-'*14} {'-'*16} {'-'*8}")
    for d in rows:
        lead = "★ " if d.is_lead else "  "
        print(f"  {d.record_id:<8} {lead}{(d.staff_name or '-')[:22]:<22} "
              f"{(d.dsl_role or '-')[:14]:<14} {(d.training_expiry or '-'):<16} "
              f"{d.training_status}")


def _show_staff() -> None:
    try:
        choices = data.list_staff_choices()
    except Exception:
        return
    if choices:
        print("  Staff:")
        for _id, label in choices:
            print(f"    {label}")


def _collect_fields(existing: data.DSLRecord | None = None,
                    *, staff_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if staff_id is not None:
        fields["staff_id"] = staff_id
    fields["dsl_role"]        = ask(f"Role ({'/'.join(DSL_ROLES)})",
                                    existing.dsl_role if existing else None)
    fields["is_lead"]         = ask("Is lead DSL? (y/n)",
                                    ("y" if existing.is_lead else "n")
                                    if existing else None)
    fields["training_date"]   = ask("Training date (YYYY-MM-DD)",
                                    existing.training_date if existing else None)
    fields["training_expiry"] = ask("Training expiry (YYYY-MM-DD)",
                                    existing.training_expiry if existing else None)
    fields["contact_number"]  = ask("Contact number",
                                    existing.contact_number if existing else None)
    fields["status"]          = ask(f"Status ({'/'.join(STATUSES)})",
                                    existing.status if existing else "active")
    fields["notes"]           = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: dsl open_manager")
    while True:
        s = data.summary()
        print("\n  ── Designated Safeguarding Lead ──")
        print(f"  Active DSLs: {s['total']}   Leads: {s['leads']}   "
              f"Deputies: {s['deputies']}   Training due: {s['training_due']}")
        _print_table(data.list_records())
        print("\n   A) Add    E) Edit    D) Delete    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add DSL ──")
    _show_staff()
    sid = _prompt("  Staff ID: ")
    if not sid:
        print("  Cancelled.")
        return
    fields = _collect_fields(staff_id=sid)
    d = data.create_record(fields)
    print(f"\n  Registered {d.staff_name} as {d.dsl_role or 'DSL'} ({d.record_id}).")


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
    d = data.update_record(rid, fields)
    print(f"\n  Updated DSL record {d.record_id}.")


@_safe
def open_delete() -> None:
    rid = _prompt("  Record ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    if data.get_record(rid) is None:
        print("  No record with that ID.")
        return
    if _prompt(f"  Delete DSL record {rid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_record(rid):
        print(f"  Deleted record {rid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Designated Safeguarding Lead": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching dsl CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
