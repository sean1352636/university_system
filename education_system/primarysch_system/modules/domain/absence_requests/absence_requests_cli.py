"""CLI handlers for absence requests."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.absence_requests import (
    absence_requests as data,
)
from education_system.primarysch_system.modules.domain.absence_requests.absence_requests import (
    REQUEST_STATUSES, ABSENCE_CATEGORIES, AUTHORISATIONS,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
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


def _print_table(rows: list[data.Request]) -> None:
    if not rows:
        print("  (no requests)")
        return
    print(f"  {'ID':<5} {'Pupil':<10} {'Yr':<3} "
          f"{'Start':<11} {'End':<11} {'Days':<5} "
          f"{'Category':<24} {'Status':<10} {'Auth':<12}")
    print(f"  {'-'*5} {'-'*10} {'-'*3} {'-'*11} {'-'*11} {'-'*5} "
          f"{'-'*24} {'-'*10} {'-'*12}")
    for r in rows:
        days = str(r.school_days) if r.school_days is not None else "-"
        print(f"  {r.request_id:<5} {r.pupil_id:<10} "
              f"{(r.pupil_year or '-'):<3} "
              f"{r.start_date:<11} {r.end_date:<11} {days:<5} "
              f"{r.category[:24]:<24} {r.status:<10} "
              f"{r.authorisation:<12}")


@_safe
def open_absence_requests() -> None:
    logger.debug("CLI: open_absence_requests")
    while True:
        print("\n  ── Absence Requests ──")
        print("   1) New request")
        print("   2) List requests")
        print("   3) View request")
        print("   4) Edit request")
        print("   5) Approve")
        print("   6) Decline")
        print("   7) Cancel")
        print("   8) Cohort summary")
        print("   9) Delete request")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new, "2": _list, "3": _view, "4": _edit,
            "5": _approve, "6": _decline, "7": _cancel,
            "8": _summary, "9": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.Request | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"]       = ask("Pupil ID",
                                existing.pupil_id if existing else None)
    f["requested_by"]   = ask("Requested by (name)",
                                existing.requested_by if existing else None)
    f["relationship"]   = ask("Relationship",
                                existing.relationship if existing else None)
    f["submitted_date"] = ask(
        "Submitted (YYYY-MM-DD, blank = today)",
        existing.submitted_date if existing else None)
    f["start_date"]     = ask("Start date (YYYY-MM-DD)",
                                existing.start_date if existing else None)
    f["end_date"]       = ask("End date (YYYY-MM-DD)",
                                existing.end_date if existing else None)
    f["school_days"]    = ask("School days (blank to auto-calc)",
                                existing.school_days if existing else None)
    f["category"]       = ask(
        f"Category ({'/'.join(ABSENCE_CATEGORIES)})",
        existing.category if existing else "Family holiday")
    f["reason"]         = ask("Reason",
                                existing.reason if existing else None)
    f["destination"]    = ask("Destination",
                                existing.destination if existing else None)
    f["status"]         = ask(
        f"Status ({'/'.join(REQUEST_STATUSES)})",
        existing.status if existing else "Pending")
    f["authorisation"]  = ask(
        f"Authorisation ({'/'.join(AUTHORISATIONS)})",
        existing.authorisation if existing else "Not yet decided")
    f["decided_by"]     = ask(
        "Decided by",
        existing.decided_by if existing else None)
    f["decided_date"]   = ask(
        "Decided date (YYYY-MM-DD)",
        existing.decided_date if existing else None)
    f["decision_notes"] = ask(
        "Decision notes",
        existing.decision_notes if existing else None)
    f["contact_phone"]  = ask(
        "Contact phone",
        existing.contact_phone if existing else None)
    f["notes"]          = ask("Notes",
                                existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── New Absence Request ──")
    fields = _collect()
    if not fields.get("pupil_id"):
        print("  Cancelled.")
        return
    r = data.create(fields)
    print(f"  Created request #{r.request_id}: {r.pupil_id} "
          f"{r.start_date}→{r.end_date} ({r.school_days} school days, "
          f"{r.status})")


@_safe
def _list() -> None:
    pid = _prompt("  Pupil ID (blank): ") or None
    yg  = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(REQUEST_STATUSES)}, blank): ") or None
    cat = _prompt(
        f"  Category ({'/'.join(ABSENCE_CATEGORIES)}, blank): ") or None
    pending_only = _prompt("  Pending only? (y/N): ").lower() == "y"
    rows = data.list_requests(
        pupil_id=pid, year_group=yg, status=status,
        category=cat, pending_only=pending_only)
    print(f"\n  {len(rows)} request(s):")
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
    rid = _ask_id("Request ID")
    if rid is None:
        return
    r = data.get(rid)
    if r is None:
        print("  No request with that ID.")
        return
    print(f"\n  ── Request #{r.request_id} ──")
    print(f"  Pupil:        {r.pupil_id} ({r.pupil_name or '-'}, "
          f"Yr {r.pupil_year or '-'})")
    print(f"  Requested by: {r.requested_by} "
          f"({r.relationship or '-'})")
    print(f"  Submitted:    {r.submitted_date}")
    print(f"  Dates:        {r.start_date} → {r.end_date} "
          f"({r.school_days} school days)")
    print(f"  Category:     {r.category}")
    print(f"  Destination:  {r.destination or '-'}")
    print(f"  Reason:       {r.reason}")
    print(f"  Status:       {r.status}    "
          f"Auth: {r.authorisation}")
    print(f"  Decided by:   {r.decided_by or '-'}    "
          f"On: {r.decided_date or '-'}")
    print(f"  Decision:     {r.decision_notes or '-'}")
    print(f"  Contact:      {r.contact_phone or '-'}")
    print(f"  Notes:        {r.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    rid = _ask_id("Request ID")
    if rid is None:
        return
    existing = data.get(rid)
    if existing is None:
        print("  No request with that ID.")
        return
    fields = _collect(existing)
    data.update(rid, fields)
    print(f"  Updated request #{rid}.")


@_safe
def _approve() -> None:
    rid = _ask_id("Request ID")
    if rid is None:
        return
    decided_by = _prompt("  Decided by: ")
    if not decided_by:
        print("  Cancelled (decided-by required).")
        return
    notes = _prompt("  Decision notes (blank): ") or None
    r = data.decide(rid, approve=True,
                       decided_by=decided_by,
                       decision_notes=notes)
    print(f"  Approved request #{r.request_id} on {r.decided_date}.")


@_safe
def _decline() -> None:
    rid = _ask_id("Request ID")
    if rid is None:
        return
    decided_by = _prompt("  Decided by: ")
    if not decided_by:
        print("  Cancelled (decided-by required).")
        return
    notes = _prompt("  Decision notes (blank): ") or None
    r = data.decide(rid, approve=False,
                       decided_by=decided_by,
                       decision_notes=notes)
    print(f"  Declined request #{r.request_id} on {r.decided_date}.")


@_safe
def _cancel() -> None:
    rid = _ask_id("Request ID")
    if rid is None:
        return
    notes = _prompt("  Cancel notes (blank): ") or None
    r = data.cancel(rid, decision_notes=notes)
    print(f"  Cancelled request #{r.request_id}.")


@_safe
def _summary() -> None:
    frm = _prompt("  From date (blank): ") or None
    to  = _prompt("  To date (blank): ") or None
    s = data.cohort_summary(from_date=frm, to_date=to)
    print(f"\n  Total: {s['total']}   Pending: {s['pending']}   "
          f"Approved: {s['approved']}   Declined: {s['declined']}   "
          f"Cancelled: {s['cancelled']}")
    print(f"  Pupils: {s['pupils']}")
    print(f"  School-day load: total {s['total_school_days']}, "
          f"approved {s['approved_school_days']}")
    print(f"  By category: "
          + "   ".join(f"{k}: {v}" for k, v in s["by_category"].items()))
    print(f"  By auth:     "
          + "   ".join(f"{k}: {v}" for k, v in s["by_auth"].items()))
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    rid = _ask_id("Request ID")
    if rid is None:
        return
    r = data.get(rid)
    if r is None:
        print("  No request with that ID.")
        return
    confirm = _prompt(
        f"  Delete request #{rid} ({r.pupil_id}, "
        f"{r.start_date}→{r.end_date})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete(rid):
        print(f"  Deleted request #{rid}.")


_DISPATCH = {"Absence Requests": open_absence_requests}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching absence_requests CLI label: %s", label)
    handler()
    return True
