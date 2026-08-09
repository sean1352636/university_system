"""CLI flow for Cohort Tracking (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.assessment.cohort_tracking import (
    cohort_tracking as data,
)
from education_system.systems.nursery.domain.assessment.cohort_tracking.cohort_tracking import (
    AREAS,
    ROOMS,
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


def _print_table(rows: list[data.Cohort]) -> None:
    if not rows:
        print("  (no cohort records)")
        return
    print(f"  {'ID':<8} {'Cohort':<28} {'Room':<16} {'Area':<32} "
          f"{'Total':>6} {'OnTrack':>8}")
    print(f"  {'-'*8} {'-'*28} {'-'*16} {'-'*32} {'-'*6} {'-'*8}")
    for c in rows:
        print(f"  {c.cohort_id:<8} {c.cohort_name[:28]:<28} "
              f"{(c.room or '-')[:16]:<16} "
              f"{(c.area or '-')[:32]:<32} "
              f"{str(c.total_children or '-'):>6} "
              f"{str(c.on_track_count or '-'):>8}")


def _print_detail(c: data.Cohort) -> None:
    print(f"\n  ── Cohort {c.cohort_id} ──")
    print(f"  Cohort name:     {c.cohort_name}")
    print(f"  Room:            {c.room or '-'}")
    print(f"  Term:            {c.term or '-'}")
    print(f"  Area:            {c.area or '-'}")
    print(f"  Assessment date: {c.assessment_date or '-'}")
    print(f"  Total children:  {c.total_children if c.total_children is not None else '-'}")
    print(f"  Below expected:  {c.below_count if c.below_count is not None else '-'}")
    print(f"  On track:        {c.on_track_count if c.on_track_count is not None else '-'}")
    print(f"  Above expected:  {c.above_count if c.above_count is not None else '-'}")
    print(f"  Staff:           {c.staff_name or c.staff_id or '-'}")
    print(f"  Notes:           {c.notes or '-'}")


def _collect_fields(existing: data.Cohort | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    fields["cohort_name"] = ask("Cohort name",
                                existing.cohort_name if existing else None)
    print(f"  Rooms: {', '.join(ROOMS)}")
    fields["room"] = ask("Room (optional)",
                         existing.room if existing else None)
    fields["term"] = ask("Term (optional)",
                         existing.term if existing else None)
    print(f"  Areas: {', '.join(AREAS)}")
    fields["area"] = ask("Area (optional)",
                         existing.area if existing else None)
    fields["assessment_date"] = ask(
        "Assessment date (YYYY-MM-DD, optional)",
        existing.assessment_date if existing else None)
    fields["total_children"] = ask(
        "Total children (optional)",
        existing.total_children if existing else None)
    fields["below_count"] = ask(
        "Below expected count (optional)",
        existing.below_count if existing else None)
    fields["on_track_count"] = ask(
        "On-track count (optional)",
        existing.on_track_count if existing else None)
    fields["above_count"] = ask(
        "Above expected count (optional)",
        existing.above_count if existing else None)
    # Staff — show list then ask for ID
    try:
        staff = data.list_staff_choices()
    except Exception:
        staff = []
    if staff:
        print("  Staff:")
        for sid, lbl in staff:
            print(f"    {lbl}")
    fields["staff_id"] = ask("Staff ID (optional)",
                             existing.staff_id if existing else None)
    fields["notes"] = ask("Notes (optional)",
                          existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: cohort_tracking open_manager")
    while True:
        print("\n  ── Cohort Tracking ──")
        _print_table(data.list_cohorts())
        print("\n   A) Add    V) View    E) Edit    D) Delete    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            cid = _prompt("  Cohort ID: ")
            c = data.get_cohort(cid)
            if c is None:
                print("  No cohort with that ID.")
            else:
                _print_detail(c)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Cohort Record ──")
    fields = _collect_fields()
    c = data.create_cohort(fields)
    print(f"\n  Added cohort record {c.cohort_id} — {c.cohort_name}.")


@_safe
def open_edit() -> None:
    cid = _prompt("  Cohort ID: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_cohort(cid)
    if existing is None:
        print("  No cohort with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    c = data.update_cohort(cid, fields)
    print(f"\n  Updated cohort record {c.cohort_id}.")


@_safe
def open_delete() -> None:
    cid = _prompt("  Cohort ID to delete: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_cohort(cid)
    if existing is None:
        print("  No cohort with that ID.")
        return
    if _prompt(
        f"  Delete '{existing.cohort_name}' ({cid})? (y/N): "
    ).lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_cohort(cid):
        print(f"  Deleted cohort record {cid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Cohort Tracking": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching cohort tracking CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
