"""CLI flow for Prevent Duty (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.prevent_duty import prevent_duty as data
from education_system.nursery_system.modules.domain.prevent_duty.prevent_duty import ValidationError

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _cell(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    return str(v)


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


def _print_table(rows) -> None:
    if not rows:
        print("  (no records)")
        return
    print("  ID         Type                  Date            Channel      Status         ")
    for rec in rows:
        print("  {:<10} {:<21} {:<15} {:<12} {:<15}".format(_cell(getattr(rec, 'record_id', None))[:10], _cell(getattr(rec, 'record_type', None))[:21], _cell(getattr(rec, 'record_date', None))[:15], _cell(getattr(rec, 'channel_referral', None))[:12], _cell(getattr(rec, 'status', None))[:15]))


def _collect_fields(existing=None) -> dict:
    def ask(label, current=None):
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict = {}
    if existing is None:
        try:
            ch = data.list_pupil_choices()
            if ch:
                print("  Children: " + ", ".join(l for _i, l in ch))
        except Exception:
            pass
    if existing is None:
        try:
            st = data.list_staff_choices()
            if st:
                print("  Staff: " + ", ".join(l for _i, l in st))
        except Exception:
            pass
    fields["record_type"] = ask("Record type (" + "/".join(x for x in data.RECORD_TYPES if x) + ")", existing.record_type if existing else None)
    fields["staff_id"] = ask("Staff (optional) (staff ID)", existing.staff_id if existing else None)
    fields["pupil_id"] = ask("Child (optional) (ID)", existing.pupil_id if existing else None)
    fields["record_date"] = ask("Date (YYYY-MM-DD)", existing.record_date if existing else None)
    fields["description"] = ask("Description", existing.description if existing else None)
    fields["action_taken"] = ask("Action taken", existing.action_taken if existing else None)
    fields["channel_referral"] = ask("Channel referral made? (y/n)", ("y" if existing.channel_referral else "n") if existing else None)
    fields["status"] = ask("Status (" + "/".join(data.STATUSES) + ")", existing.status if existing else "open")
    fields["notes"] = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    while True:
        s = data.summary()
        print("\n  \u2500\u2500 Prevent Duty \u2500\u2500")
        print(f"  Records: {s['total']}   Open: {s['open']}")
        _print_table(data.list_records())
        print("\n   A) Add    V) View    E) Edit    D) Delete    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            _add()
        elif choice == "v":
            rid = _prompt("  Record ID: ")
            rec = data.get_record(rid)
            if rec is None:
                print("  No record with that ID.")
            else:
                for f in rec.__dataclass_fields__:
                    print(f"  {f}: {getattr(rec, f)}")
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            _edit()
        elif choice == "d":
            _delete()
        else:
            print("  Invalid selection.")


@_safe
def _add() -> None:
    print("\n  \u2500\u2500 Add record \u2500\u2500")
    rec = data.create_record(_collect_fields())
    print(f"\n  Created {rec.record_id}.")


@_safe
def _edit() -> None:
    rid = _prompt("  Record ID: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    rec = data.update_record(rid, _collect_fields(existing))
    print(f"\n  Updated {rec.record_id}.")


@_safe
def _delete() -> None:
    rid = _prompt("  Record ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    if data.get_record(rid) is None:
        print("  No record with that ID.")
        return
    if _prompt(f"  Delete {rid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    print(f"  Deleted {rid}." if data.delete_record(rid) else "  Could not delete.")


_DISPATCH = {"Prevent Duty": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
