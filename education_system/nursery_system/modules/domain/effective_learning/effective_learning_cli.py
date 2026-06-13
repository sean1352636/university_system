"""CLI flow for Characteristics of Effective Learning (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.effective_learning import (
    effective_learning as data,
)
from education_system.nursery_system.modules.domain.effective_learning.effective_learning import (
    CHARACTERISTICS,
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


def _print_records(rows: list[data.EffectiveLearning]) -> None:
    if not rows:
        print("  (no effective learning records)")
        return
    print(f"  {'ID':<8} {'Child':<22} {'Date':<12} {'Characteristic':<32} "
          f"{'Aspect'}")
    print(f"  {'-'*8} {'-'*22} {'-'*12} {'-'*32} {'-'*20}")
    for r in rows:
        print(f"  {r.record_id:<8} {(r.child_name or '-')[:22]:<22} "
              f"{(r.observation_date or '-'):<12} "
              f"{(r.characteristic or '-')[:32]:<32} "
              f"{(r.aspect or '-')[:20]}")


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


def _collect_fields(existing: data.EffectiveLearning | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["observation_date"] = ask("Observation date (YYYY-MM-DD)",
                                     existing.observation_date if existing else None)
    fields["characteristic"]   = ask(
        f"Characteristic ({'/'.join(CHARACTERISTICS)})",
        existing.characteristic if existing else None)
    fields["aspect"]           = ask("Aspect",
                                     existing.aspect if existing else None)
    fields["description"]      = ask("Description",
                                     existing.description if existing else None)
    _show_staff()
    fields["staff_id"]         = ask("Staff ID",
                                     existing.staff_id if existing else None)
    fields["notes"]            = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: effective_learning open_manager")
    while True:
        print("\n  ── Characteristics of Effective Learning ──")
        _print_records(data.list_records())
        print("\n   A) Add    V) View    E) Edit    D) Delete")
        print("   F) Filter by child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            rid = _prompt("  Record ID: ")
            rec = data.get_record(rid)
            if rec is None:
                print("  No record with that ID.")
            else:
                _print_detail(rec)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "f":
            pid = _prompt("  Child ID: ")
            _print_records(data.list_records(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


def _print_detail(rec: data.EffectiveLearning) -> None:
    print(f"\n  ── Effective Learning record {rec.record_id} ──")
    print(f"  Child:          {rec.child_name or '-'} ({rec.pupil_id})")
    print(f"  Date:           {rec.observation_date or '-'}")
    print(f"  Characteristic: {rec.characteristic or '-'}")
    print(f"  Aspect:         {rec.aspect or '-'}")
    print(f"  Description:    {rec.description or '-'}")
    print(f"  Staff:          {rec.staff_name or rec.staff_id or '-'}")
    print(f"  Notes:          {rec.notes or '-'}")


@_safe
def open_add() -> None:
    print("\n  ── Add Effective Learning Record ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    rec = data.create_record(fields)
    print(f"\n  Logged effective learning record {rec.record_id} for {rec.child_name}.")


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
    rec = data.update_record(rid, fields)
    print(f"\n  Updated effective learning record {rec.record_id}.")


@_safe
def open_delete() -> None:
    rid = _prompt("  Record ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    if data.get_record(rid) is None:
        print("  No record with that ID.")
        return
    if _prompt(f"  Delete record {rid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_record(rid):
        print(f"  Deleted record {rid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Characteristics of Effective Learning": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching effective_learning CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
