"""CLI handlers for attendance concerns."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.primary.domain.pastoral.attendance_concerns import (
    attendance_concerns as data,
)
from education_system.systems.primary.domain.pastoral.attendance_concerns.attendance_concerns import (
    CONCERN_STATUSES, CONCERN_LEVELS, CONCERN_TYPES,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
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
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_table(rows: list[data.Concern]) -> None:
    if not rows:
        print("  (no concerns)")
        return
    print(f"  {'ID':<5} {'Pupil':<10} {'Yr':<3} {'AY':<10} "
          f"{'Type':<20} {'Att%':<6} {'Status':<12} {'Opened':<10}")
    print(f"  {'-'*5} {'-'*10} {'-'*3} {'-'*10} {'-'*20} {'-'*6} "
          f"{'-'*12} {'-'*10}")
    for c in rows:
        att = f"{c.attendance_pct:.1f}" if c.attendance_pct is not None else "-"
        print(f"  {c.concern_id:<5} {c.pupil_id:<10} "
              f"{(c.pupil_year or '-'):<3} {c.academic_year:<10} "
              f"{c.concern_type[:20]:<20} {att:<6} "
              f"{c.status:<12} {c.opened_date:<10}")


@_safe
def open_attendance_concerns() -> None:
    logger.debug("CLI: open_attendance_concerns")
    while True:
        print("\n  ── Attendance Concerns ──")
        print("   1) New concern")
        print("   2) List concerns")
        print("   3) View concern")
        print("   4) Edit concern")
        print("   5) Set status")
        print("   6) Close concern")
        print("   7) Cohort summary")
        print("   8) Delete concern")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new, "2": _list, "3": _view,
            "4": _edit, "5": _set_status, "6": _close,
            "7": _summary, "8": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.Concern | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"] = ask("Pupil ID",
                          existing.pupil_id if existing else None)
    f["academic_year"] = ask(
        "Academic year (YYYY/YY)",
        existing.academic_year if existing else None)
    f["concern_type"]  = ask(
        f"Type ({'/'.join(CONCERN_TYPES)})",
        existing.concern_type if existing else "Persistent absence")
    f["level"]         = ask(
        f"Level ({' | '.join(CONCERN_LEVELS)})",
        existing.level if existing else "PA threshold (<90%)")
    f["attendance_pct"] = ask(
        "Attendance % (blank ok)",
        existing.attendance_pct if existing else None)
    f["threshold_pct"]  = ask(
        "Threshold % (default 90.0)",
        existing.threshold_pct if existing else 90.0)
    f["opened_date"]    = ask(
        "Opened date (YYYY-MM-DD, blank = today)",
        existing.opened_date if existing else None)
    f["next_review_date"] = ask(
        "Next review date (blank ok)",
        existing.next_review_date if existing else None)
    f["closed_date"]    = ask(
        "Closed date (blank ok)",
        existing.closed_date if existing else None)
    f["status"]         = ask(
        f"Status ({'/'.join(CONCERN_STATUSES)})",
        existing.status if existing else "Open")
    f["key_worker"]     = ask("Key worker",
                                existing.key_worker if existing else None)
    f["intervention"]   = ask("Intervention",
                                existing.intervention if existing else None)
    f["parent_contact"] = ask("Parent contact",
                                existing.parent_contact if existing else None)
    f["notes"]          = ask("Notes",
                                existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── New Attendance Concern ──")
    fields = _collect()
    if not fields.get("pupil_id"):
        print("  Cancelled.")
        return
    c = data.create(fields)
    print(f"  Created concern #{c.concern_id}: {c.pupil_id} — "
          f"{c.concern_type} ({c.level}, {c.status})")


@_safe
def _list() -> None:
    pid = _prompt("  Pupil ID (blank): ") or None
    ay  = _prompt("  Academic year (blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(CONCERN_STATUSES)}, blank): ") or None
    ctype  = _prompt(
        f"  Type ({'/'.join(CONCERN_TYPES)}, blank): ") or None
    only_open = _prompt("  Open only? (y/N): ").lower() == "y"
    rows = data.list_concerns(
        pupil_id=pid, academic_year=ay, status=status,
        concern_type=ctype, open_only=only_open)
    print(f"\n  {len(rows)} concern(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_id(label: str) -> int | None:
    raw = _prompt(f"  {label}: ")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"  {label} must be a number.")
        return None


@_safe
def _view() -> None:
    cid = _ask_id("Concern ID")
    if cid is None:
        return
    c = data.get(cid)
    if c is None:
        print("  No concern with that ID.")
        return
    print(f"\n  ── Concern #{c.concern_id} ──")
    print(f"  Pupil:        {c.pupil_id} ({c.pupil_name or '-'}, "
          f"Yr {c.pupil_year or '-'})")
    print(f"  Year:         {c.academic_year}")
    print(f"  Type:         {c.concern_type}")
    print(f"  Level:        {c.level}")
    att = (f"{c.attendance_pct:.1f}%"
            if c.attendance_pct is not None else "-")
    print(f"  Attendance:   {att}   (threshold "
          f"{c.threshold_pct:.1f}%)")
    print(f"  Opened:       {c.opened_date}")
    print(f"  Next review:  {c.next_review_date or '-'}")
    print(f"  Closed:       {c.closed_date or '-'}")
    print(f"  Status:       {c.status}")
    print(f"  Key worker:   {c.key_worker or '-'}")
    print(f"  Intervention: {c.intervention or '-'}")
    print(f"  Parent ctc:   {c.parent_contact or '-'}")
    print(f"  Notes:        {c.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    cid = _ask_id("Concern ID")
    if cid is None:
        return
    existing = data.get(cid)
    if existing is None:
        print("  No concern with that ID.")
        return
    fields = _collect(existing)
    data.update(cid, fields)
    print(f"  Updated concern #{cid}.")


@_safe
def _set_status() -> None:
    cid = _ask_id("Concern ID")
    if cid is None:
        return
    c = data.get(cid)
    if c is None:
        print("  No concern with that ID.")
        return
    print(f"  Current: {c.status}")
    print(f"  Allowed: {', '.join(CONCERN_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    c = data.set_status(cid, new)
    print(f"  Status now: {c.status}")


@_safe
def _close() -> None:
    cid = _ask_id("Concern ID")
    if cid is None:
        return
    end = _prompt("  Closed date (YYYY-MM-DD, blank = today): ")
    c = data.close(cid, closed_date=end.strip() or None)
    print(f"  Closed concern #{c.concern_id} on {c.closed_date}.")


@_safe
def _summary() -> None:
    ay = _prompt("  Academic year (blank): ") or None
    s = data.cohort_summary(academic_year=ay)
    print(f"\n  Total: {s['total']}   Open: {s['open']}   "
          f"Pupils: {s['pupils']}")
    if s["avg_attendance"] is not None:
        print(f"  Avg attendance: {s['avg_attendance']:.2f}%")
    print("  By status: "
          + "   ".join(f"{k}: {v}" for k, v in s["by_status"].items()))
    print("  By type:   "
          + "   ".join(f"{k}: {v}" for k, v in s["by_type"].items()))
    print("  By level:  "
          + "   ".join(f"{k}: {v}" for k, v in s["by_level"].items()))
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    cid = _ask_id("Concern ID")
    if cid is None:
        return
    c = data.get(cid)
    if c is None:
        print("  No concern with that ID.")
        return
    confirm = _prompt(
        f"  Delete concern #{cid} ({c.pupil_id} / "
        f"{c.concern_type})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete(cid):
        print(f"  Deleted concern #{cid}.")


_DISPATCH = {"Attendance Concerns": open_attendance_concerns}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching attendance_concerns CLI label: %s",
                  label)
    handler()
    return True
