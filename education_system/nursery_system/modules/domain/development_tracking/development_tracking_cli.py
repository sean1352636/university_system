"""CLI flow for Development Tracking (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.development_tracking import (
    development_tracking as data,
)
from education_system.nursery_system.modules.domain.development_tracking.development_tracking import (
    AGE_BANDS,
    AREAS,
    JUDGEMENTS,
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


def _print_records(rows: list[data.DevRecord]) -> None:
    if not rows:
        print("  (no development tracking records)")
        return
    print(f"  {'ID':<8} {'Child':<22} {'Area':<36} {'Band':<22} "
          f"{'Judgement':<12} {'Date'}")
    print(f"  {'-'*8} {'-'*22} {'-'*36} {'-'*22} {'-'*12} {'-'*12}")
    for r in rows:
        print(f"  {r.record_id:<8} {(r.child_name or '-')[:22]:<22} "
              f"{(r.area or '-')[:36]:<36} {(r.age_band or '-')[:22]:<22} "
              f"{(r.judgement or '-'):<12} {r.assessment_date or '-'}")


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


def _collect_fields(existing: data.DevRecord | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["area"]            = ask(f"Area ({'/'.join(AREAS)})",
                                    existing.area if existing else None)
    fields["aspect"]          = ask("Aspect (free text)",
                                    existing.aspect if existing else None)
    fields["age_band"]        = ask(f"Age band ({'/'.join(AGE_BANDS)})",
                                    existing.age_band if existing else None)
    fields["judgement"]       = ask(f"Judgement ({'/'.join(JUDGEMENTS)})",
                                    existing.judgement if existing else None)
    fields["assessment_date"] = ask("Assessment date (YYYY-MM-DD)",
                                    existing.assessment_date if existing else None)
    _show_staff()
    fields["assessor"]        = ask("Assessor (staff ID)",
                                    existing.assessor if existing else None)
    fields["next_steps"]      = ask("Next steps",
                                    existing.next_steps if existing else None)
    fields["notes"]           = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: development_tracking open_manager")
    while True:
        print("\n  ── Development Tracking (Prime & Specific Areas) ──")
        _print_records(data.list_records())
        print("\n   A) Add    V) View    E) Edit    D) Delete    F) Filter by child")
        print("   0) Back")
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


def _print_detail(r: data.DevRecord) -> None:
    print(f"\n  ── Development Tracking record {r.record_id} ──")
    print(f"  Child:           {r.child_name or '-'} ({r.pupil_id})")
    print(f"  Area:            {r.area or '-'}")
    print(f"  Aspect:          {r.aspect or '-'}")
    print(f"  Age band:        {r.age_band or '-'}")
    print(f"  Judgement:       {r.judgement or '-'}")
    print(f"  Assessment date: {r.assessment_date or '-'}")
    print(f"  Assessor:        {r.assessor_name or r.assessor or '-'}")
    print(f"  Next steps:      {r.next_steps or '-'}")
    print(f"  Notes:           {r.notes or '-'}")


@_safe
def open_add() -> None:
    print("\n  ── Add Development Tracking Record ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    rec = data.create_record(fields)
    print(f"\n  Added development tracking record {rec.record_id} for {rec.child_name}.")


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
    print(f"\n  Updated development tracking record {rec.record_id}.")


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


_DISPATCH = {"Development Tracking (Prime & Specific Areas)": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching development_tracking CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
