"""CLI handlers for pupil-support plans."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.primary.domain.pastoral.pupil_support import (
    pupil_support as data,
)
from education_system.systems.primary.domain.pastoral.pupil_support.pupil_support import (
    PLAN_TYPES, PLAN_STATUSES, PRIORITIES, REVIEW_OUTCOMES,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
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


def _print_plans(rows: list[data.SupportPlan]) -> None:
    if not rows:
        print("  (no plans)")
        return
    print(f"  {'ID':<4} {'AYear':<8} {'Pupil':<10} {'Yr':<3} "
          f"{'Type':<14} {'Pri':<9} {'Status':<11} "
          f"{'Next review':<11} {'Title':<28}")
    print(f"  {'-'*4} {'-'*8} {'-'*10} {'-'*3} {'-'*14} {'-'*9} "
          f"{'-'*11} {'-'*11} {'-'*28}")
    for p in rows:
        print(f"  {p.plan_id:<4} {p.academic_year:<8} {p.pupil_id:<10} "
              f"{(p.pupil_year or '-'):<3} "
              f"{p.plan_type[:14]:<14} {p.priority:<9} "
              f"{p.status:<11} "
              f"{(p.next_review_date or '-'):<11} "
              f"{p.title[:28]:<28}")


def _print_reviews(rows: list[data.SupportReview]) -> None:
    if not rows:
        print("  (no reviews)")
        return
    print(f"  {'ID':<5} {'Date':<10} {'Reviewer':<20} "
          f"{'Outcome':<12} {'Next':<11} {'Progress':<32}")
    print(f"  {'-'*5} {'-'*10} {'-'*20} {'-'*12} {'-'*11} {'-'*32}")
    for r in rows:
        print(f"  {r.review_id:<5} {r.review_date:<10} "
              f"{(r.reviewer or '-')[:20]:<20} "
              f"{r.outcome:<12} {(r.next_review_date or '-'):<11} "
              f"{(r.progress or '-')[:32]:<32}")


@_safe
def open_pupil_support() -> None:
    logger.debug("CLI: open_pupil_support")
    while True:
        print("\n  ── Pupil Support ──")
        print("  Plans")
        print("    1) New plan")
        print("    2) List plans")
        print("    3) View plan + reviews")
        print("    4) Edit plan")
        print("    5) Set status")
        print("    6) Delete plan")
        print("  Reviews")
        print("    7) Add review")
        print("    8) Delete review")
        print("  Reports")
        print("    9) Cohort summary")
        print("   10) Overdue reviews")
        print("    0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new, "2": _list, "3": _view,
            "4": _edit, "5": _set_status, "6": _delete,
            "7": _add_review, "8": _delete_review,
            "9": _summary, "10": _overdue,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.SupportPlan | None = None
              ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"]         = ask("Pupil ID",
                                     existing.pupil_id if existing
                                     else None)
    f["academic_year"]    = ask("Academic year (YYYY/YY)",
                                     existing.academic_year if existing
                                     else None)
    f["plan_type"]        = ask(f"Type ({'/'.join(PLAN_TYPES)})",
                                     existing.plan_type if existing
                                     else "Academic")
    f["title"]            = ask("Title",
                                     existing.title if existing else None)
    f["target"]           = ask("Target",
                                     existing.target if existing else None)
    f["success_criteria"] = ask("Success criteria",
                                     existing.success_criteria if existing
                                     else None)
    f["coordinator"]      = ask("Coordinator",
                                     existing.coordinator if existing
                                     else None)
    f["priority"]         = ask(f"Priority ({'/'.join(PRIORITIES)})",
                                     existing.priority if existing
                                     else "Medium")
    f["start_date"]       = ask("Start date (YYYY-MM-DD, blank = today)",
                                     existing.start_date if existing
                                     else None)
    f["end_date"]         = ask("End date (YYYY-MM-DD, blank ok)",
                                     existing.end_date if existing
                                     else None)
    f["next_review_date"] = ask("Next review date (blank ok)",
                                     existing.next_review_date if existing
                                     else None)
    f["status"]           = ask(f"Status ({'/'.join(PLAN_STATUSES)})",
                                     existing.status if existing
                                     else "Draft")
    f["outcome"]          = ask("Outcome (required if Complete/Closed)",
                                     existing.outcome if existing else None)
    f["notes"]            = ask("Notes",
                                     existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── New Support Plan ──")
    fields = _collect()
    p = data.create_plan(fields)
    print(f"  Created plan #{p.plan_id}: {p.title} "
          f"({p.plan_type}, {p.priority}, {p.status})")


@_safe
def _list() -> None:
    pid = _prompt("  Pupil ID (blank): ") or None
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    ay = _prompt("  Academic year (blank): ") or None
    ptype = _prompt(f"  Type ({'/'.join(PLAN_TYPES)}, blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(PLAN_STATUSES)}, blank): ") or None
    pri = _prompt(f"  Priority ({'/'.join(PRIORITIES)}, blank): ") or None
    rows = data.list_plans(pupil_id=pid, year_group=yg,
                              academic_year=ay,
                              plan_type=ptype, status=status,
                              priority=pri)
    print(f"\n  {len(rows)} plan(s):")
    _print_plans(rows)
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
    pid = _ask_id("Plan ID")
    if pid is None:
        return
    s = data.plan_summary(pid)
    p = s["plan"]
    print(f"\n  ── Plan #{p.plan_id} ──")
    print(f"  Pupil:     {p.pupil_id} ({p.pupil_name or '-'}, "
          f"Yr {p.pupil_year or '-'})")
    print(f"  Year:      {p.academic_year}")
    print(f"  Type:      {p.plan_type}    Priority: {p.priority}")
    print(f"  Title:     {p.title}")
    print(f"  Target:    {p.target or '-'}")
    print(f"  Success:   {p.success_criteria or '-'}")
    print(f"  Coord:     {p.coordinator or '-'}")
    print(f"  Period:    {p.start_date} → {p.end_date or 'open'}    "
          f"Next review: {p.next_review_date or '-'}")
    print(f"  Status:    {p.status}    Outcome: {p.outcome or '-'}")
    print(f"  Notes:     {p.notes or '-'}")
    print(f"\n  Reviews: {s['review_count']}    "
          f"Last: {s['last_review'] or '-'}")
    if s["by_outcome"]:
        print("  By outcome: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_outcome"].items()))
    _print_reviews(s["reviews"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    pid = _ask_id("Plan ID")
    if pid is None:
        return
    existing = data.get_plan(pid)
    if existing is None:
        print("  No plan with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect(existing)
    p = data.update_plan(pid, fields)
    print(f"  Updated plan #{p.plan_id} (status {p.status})")


@_safe
def _set_status() -> None:
    pid = _ask_id("Plan ID")
    if pid is None:
        return
    p = data.get_plan(pid)
    if p is None:
        print("  No plan with that ID.")
        return
    print(f"  Current: {p.status}    Allowed: "
          f"{', '.join(PLAN_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    outcome = None
    if new in ("Complete", "Closed"):
        outcome = _prompt("  Outcome: ")
        if not outcome:
            print("  Outcome required.")
            return
    p = data.set_status(pid, new, outcome=outcome)
    print(f"  Status now: {p.status}")


@_safe
def _delete() -> None:
    pid = _ask_id("Plan ID")
    if pid is None:
        return
    p = data.get_plan(pid)
    if p is None:
        print("  No plan with that ID.")
        return
    confirm = _prompt(
        f"  Delete plan #{pid} ({p.title}) and ALL its reviews? "
        f"(y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_plan(pid)
    print(f"  Deleted plan #{pid}.")


@_safe
def _add_review() -> None:
    pid = _ask_id("Plan ID")
    if pid is None:
        return
    if data.get_plan(pid) is None:
        print("  No plan with that ID.")
        return
    f: dict[str, Any] = {"plan_id": pid}
    f["review_date"] = _prompt(
        "  Review date (YYYY-MM-DD, blank = today): ") or None
    f["reviewer"]    = _prompt("  Reviewer: ") or None
    f["progress"]    = _prompt("  Progress: ") or None
    f["next_steps"]  = _prompt("  Next steps: ") or None
    f["outcome"]     = _prompt(
        f"  Outcome ({'/'.join(REVIEW_OUTCOMES)}) [On track]: "
    ) or "On track"
    f["next_review_date"] = _prompt(
        "  Next review date (blank ok): ") or None
    f["notes"]       = _prompt("  Notes: ") or None
    r = data.add_review(f)
    print(f"  Added review #{r.review_id} ({r.outcome}, next "
          f"{r.next_review_date or '-'})")


@_safe
def _delete_review() -> None:
    rid = _ask_id("Review ID")
    if rid is None:
        return
    r = data.get_review(rid)
    if r is None:
        print("  No review with that ID.")
        return
    confirm = _prompt(f"  Delete review #{rid}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_review(rid)
    print(f"  Deleted review #{rid}.")


@_safe
def _summary() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    ay = _prompt("  Academic year (blank): ") or None
    s = data.cohort_summary(year_group=yg, academic_year=ay)
    print(f"\n  Total: {s['total']}    Active: {s['active']}")
    if s["by_status"]:
        print("  By status:   "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    if s["by_priority"]:
        print("  By priority: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_priority"].items()))
    if s["by_type"]:
        print("  By type:")
        for k, v in sorted(s["by_type"].items(),
                            key=lambda kv: -kv[1]):
            print(f"    {k:<18} {v}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _overdue() -> None:
    rows = data.overdue_reviews()
    print(f"\n  {len(rows)} Active plan(s) with overdue reviews:")
    _print_plans(rows)
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Pupil Support": open_pupil_support}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching pupil_support CLI label: %s", label)
    handler()
    return True
