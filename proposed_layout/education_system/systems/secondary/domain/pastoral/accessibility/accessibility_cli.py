"""CLI handlers for accessibility arrangements."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.pastoral.accessibility import (
    accessibility as data,
)
from education_system.systems.secondary.domain.pastoral.accessibility.accessibility import (
    ARRANGEMENT_TYPES, CATEGORIES, STATUSES, EVIDENCE_SOURCES,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
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


def _print_table(rows: list[data.Arrangement]) -> None:
    if not rows:
        print("  (no arrangements)")
        return
    print(f"  {'ID':<4} {'Start':<10} {'Pupil':<10} {'Yr':<3} "
          f"{'Type':<22} {'Category':<24} {'Exam':<5} "
          f"{'Status':<11} {'Approved by':<16}")
    print(f"  {'-'*4} {'-'*10} {'-'*10} {'-'*3} {'-'*22} {'-'*24} "
          f"{'-'*5} {'-'*11} {'-'*16}")
    for a in rows:
        print(f"  {a.arrangement_id:<4} {a.start_date:<10} "
              f"{a.pupil_id:<10} {(a.pupil_year or '-'):<3} "
              f"{a.arrangement_type[:22]:<22} "
              f"{a.category[:24]:<24} "
              f"{('Yes' if a.exam_only else 'No'):<5} "
              f"{a.status:<11} "
              f"{(a.approved_by or '-')[:16]:<16}")


@_safe
def open_accessibility() -> None:
    logger.debug("CLI: open_accessibility")
    while True:
        print("\n  ── Accessibility ──")
        print("   1) New arrangement")
        print("   2) List arrangements")
        print("   3) View arrangement")
        print("   4) Edit arrangement")
        print("   5) Set status")
        print("   6) Pupil arrangements")
        print("   7) Expired (Active but past end-date)")
        print("   8) Cohort summary")
        print("   9) Delete arrangement")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new, "2": _list, "3": _view, "4": _edit,
            "5": _set_status, "6": _pupil,
            "7": _expired, "8": _summary, "9": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.Arrangement | None = None
              ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"]         = ask("Pupil ID",
                                     existing.pupil_id if existing else None)
    f["arrangement_type"] = ask(
        f"Type ({'/'.join(ARRANGEMENT_TYPES)})",
        existing.arrangement_type if existing
        else "Reasonable adjustment")
    if not existing:
        print("  Common categories:")
        for c in CATEGORIES:
            print(f"    • {c}")
    f["category"]         = ask("Category",
                                     existing.category if existing
                                     else None)
    f["description"]      = ask("Description",
                                     existing.description if existing
                                     else None)
    exam = ask("Exam only? (y/n)",
                "y" if existing and existing.exam_only else "n")
    f["exam_only"] = exam.lower().startswith("y")
    f["start_date"]       = ask("Start date (YYYY-MM-DD, blank = today)",
                                     existing.start_date if existing
                                     else None)
    f["end_date"]         = ask("End date (YYYY-MM-DD, blank ok)",
                                     existing.end_date if existing
                                     else None)
    f["status"]           = ask(f"Status ({'/'.join(STATUSES)})",
                                     existing.status if existing
                                     else "Proposed")
    f["evidence_source"]  = ask(
        f"Evidence source ({'/'.join(EVIDENCE_SOURCES)}, blank ok)",
        existing.evidence_source if existing else None)
    f["evidence_reference"] = ask(
        "Evidence reference (blank ok)",
        existing.evidence_reference if existing else None)
    f["approved_by"]      = ask("Approved by",
                                     existing.approved_by if existing
                                     else None)
    f["approval_date"]    = ask("Approval date (YYYY-MM-DD, blank ok)",
                                     existing.approval_date if existing
                                     else None)
    f["review_date"]      = ask("Review date (YYYY-MM-DD, blank ok)",
                                     existing.review_date if existing
                                     else None)
    f["notes"]            = ask("Notes",
                                     existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── New Arrangement ──")
    fields = _collect()
    a = data.create(fields)
    print(f"  Created arrangement #{a.arrangement_id}: "
          f"{a.pupil_id} — {a.category} "
          f"(exam-only={a.exam_only}, {a.status})")


@_safe
def _list() -> None:
    pid = _prompt("  Pupil ID (blank): ") or None
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    atype = _prompt(
        f"  Type ({'/'.join(ARRANGEMENT_TYPES)}, blank): ") or None
    status = _prompt(f"  Status ({'/'.join(STATUSES)}, blank): ") or None
    exam_raw = _prompt("  Exam only? (y/n/blank): ").lower()
    exam_only = None
    if exam_raw.startswith("y"):
        exam_only = True
    elif exam_raw.startswith("n"):
        exam_only = False
    rows = data.list_arrangements(pupil_id=pid, year_group=yg,
                                    arrangement_type=atype,
                                    status=status, exam_only=exam_only)
    print(f"\n  {len(rows)} arrangement(s):")
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
    aid = _ask_id("Arrangement ID")
    if aid is None:
        return
    a = data.get(aid)
    if a is None:
        print("  No arrangement with that ID.")
        return
    print(f"\n  ── Arrangement #{a.arrangement_id} ──")
    print(f"  Pupil:        {a.pupil_id} ({a.pupil_name or '-'}, "
          f"Yr {a.pupil_year or '-'})")
    print(f"  Type:         {a.arrangement_type}")
    print(f"  Category:     {a.category}")
    print(f"  Description:  {a.description or '-'}")
    print(f"  Exam only:    {'Yes' if a.exam_only else 'No'}")
    print(f"  Period:       {a.start_date} → {a.end_date or 'open'}")
    print(f"  Status:       {a.status}    "
          f"{'(EXPIRED)' if a.expired else ''}")
    print(f"  Evidence:     {a.evidence_source or '-'}    "
          f"ref: {a.evidence_reference or '-'}")
    print(f"  Approved by:  {a.approved_by or '-'}    "
          f"on {a.approval_date or '-'}")
    print(f"  Review date:  {a.review_date or '-'}")
    print(f"  Notes:        {a.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    aid = _ask_id("Arrangement ID")
    if aid is None:
        return
    existing = data.get(aid)
    if existing is None:
        print("  No arrangement with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect(existing)
    a = data.update(aid, fields)
    print(f"  Updated arrangement #{a.arrangement_id} "
          f"(status {a.status})")


@_safe
def _set_status() -> None:
    aid = _ask_id("Arrangement ID")
    if aid is None:
        return
    a = data.get(aid)
    if a is None:
        print("  No arrangement with that ID.")
        return
    print(f"  Current: {a.status}    Allowed: "
          f"{', '.join(STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    a = data.set_status(aid, new)
    print(f"  Status now: {a.status}")


@_safe
def _pupil() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    only_active = _prompt(
        "  Active only? (y/N): ").lower().startswith("y")
    rows = data.pupil_arrangements(pid, active_only=only_active)
    print(f"\n  {len(rows)} arrangement(s) for {pid}:")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _expired() -> None:
    rows = data.expired_arrangements()
    print(f"\n  {len(rows)} Active arrangement(s) past their end date:")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    s = data.cohort_summary(year_group=yg)
    print(f"\n  Total: {s['total']}    Active: {s['active']}    "
          f"Exam-only: {s['exam_only']}    "
          f"Expired but Active: {s['expired_active']}")
    if s["by_type"]:
        print("  By type:")
        for k, v in sorted(s["by_type"].items(),
                            key=lambda kv: -kv[1]):
            print(f"    {k:<24} {v}")
    if s["by_status"]:
        print("  By status: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    if s["by_category"]:
        print("  Top categories:")
        for k, v in sorted(s["by_category"].items(),
                            key=lambda kv: -kv[1])[:10]:
            print(f"    {k:<26} {v}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    aid = _ask_id("Arrangement ID")
    if aid is None:
        return
    a = data.get(aid)
    if a is None:
        print("  No arrangement with that ID.")
        return
    confirm = _prompt(
        f"  Delete arrangement #{aid} ({a.pupil_id}, "
        f"{a.category})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete(aid)
    print(f"  Deleted arrangement #{aid}.")


_DISPATCH = {"Accessibility": open_accessibility}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching accessibility CLI label: %s", label)
    handler()
    return True
