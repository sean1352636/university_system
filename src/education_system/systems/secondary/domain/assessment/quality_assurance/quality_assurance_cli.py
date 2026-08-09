"""CLI handlers for quality-assurance reviews."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.quality_assurance import (
    quality_assurance as data,
)
from education_system.systems.secondary.domain.assessment.quality_assurance.quality_assurance import (
    REVIEW_TYPES, REVIEW_STATUSES, JUDGEMENTS, ACTION_STATUSES,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
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


def _print_reviews(rows: list[data.QAReview]) -> None:
    if not rows:
        print("  (no reviews)")
        return
    print(f"  {'ID':<4} {'Date':<10} {'Type':<18} {'Focus':<22} "
          f"{'Lead':<18} {'Status':<10} {'Judgement':<22}")
    print(f"  {'-'*4} {'-'*10} {'-'*18} {'-'*22} {'-'*18} {'-'*10} "
          f"{'-'*22}")
    for r in rows:
        print(f"  {r.review_id:<4} {r.review_date:<10} "
              f"{r.review_type[:18]:<18} "
              f"{(r.focus_area or '-')[:22]:<22} "
              f"{r.lead_reviewer[:18]:<18} {r.status:<10} "
              f"{r.judgement[:22]:<22}")


def _print_actions(rows: list[data.QAAction]) -> None:
    if not rows:
        print("  (no actions)")
        return
    print(f"  {'ID':<5} {'Rev':<4} {'Due':<10} {'OD':<3} "
          f"{'Status':<11} {'Owner':<18} {'Action':<40}")
    print(f"  {'-'*5} {'-'*4} {'-'*10} {'-'*3} {'-'*11} {'-'*18} "
          f"{'-'*40}")
    for a in rows:
        print(f"  {a.action_id:<5} {a.review_id:<4} "
              f"{(a.due_date or '-'):<10} "
              f"{('!' if a.overdue else '-'):<3} "
              f"{a.status:<11} {(a.owner or '-')[:18]:<18} "
              f"{a.action[:40]:<40}")


@_safe
def open_quality_assurance() -> None:
    logger.debug("CLI: open_quality_assurance")
    while True:
        print("\n  ── Quality Assurance ──")
        print("  Reviews")
        print("    1) New review")
        print("    2) List reviews")
        print("    3) View review + actions")
        print("    4) Edit review")
        print("    5) Set review status")
        print("    6) Delete review")
        print("  Actions")
        print("    7) Add action")
        print("    8) List actions (overdue toggle)")
        print("    9) Edit action")
        print("   10) Delete action")
        print("  Reports")
        print("   11) Cohort summary")
        print("    0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new_review, "2": _list_reviews, "3": _view,
            "4": _edit_review, "5": _set_status,
            "6": _delete_review,
            "7": _add_action, "8": _list_actions,
            "9": _edit_action, "10": _delete_action,
            "11": _summary,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect_review(existing: data.QAReview | None = None
                     ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["title"]         = ask("Title",
                                existing.title if existing else None)
    f["review_type"]   = ask(f"Type ({'/'.join(REVIEW_TYPES)})",
                                existing.review_type if existing
                                else "Department")
    f["focus_area"]    = ask("Focus area",
                                existing.focus_area if existing
                                else None)
    f["lead_reviewer"] = ask("Lead reviewer",
                                existing.lead_reviewer if existing
                                else None)
    f["additional_team"] = ask("Additional reviewers",
                                  existing.additional_team if existing
                                  else None)
    f["review_date"]   = ask("Review date (YYYY-MM-DD, blank = today)",
                                existing.review_date if existing
                                else None)
    f["status"]        = ask(f"Status ({'/'.join(REVIEW_STATUSES)})",
                                existing.status if existing else "Planned")
    f["judgement"]     = ask(f"Judgement ({'/'.join(JUDGEMENTS)})",
                                existing.judgement if existing
                                else "Not judged")
    f["strengths"]     = ask("Strengths",
                                existing.strengths if existing else None)
    f["areas_for_development"] = ask(
        "Areas for development",
        existing.areas_for_development if existing else None)
    f["summary"]       = ask("Summary",
                                existing.summary if existing else None)
    f["follow_up_date"] = ask("Follow-up date (YYYY-MM-DD, blank ok)",
                                 existing.follow_up_date if existing
                                 else None)
    f["notes"]         = ask("Notes",
                                existing.notes if existing else None)
    return f


@_safe
def _new_review() -> None:
    print("\n  ── New QA Review ──")
    fields = _collect_review()
    r = data.create_review(fields)
    print(f"  Created review #{r.review_id} '{r.title}' "
          f"({r.review_type}, {r.status})")


@_safe
def _list_reviews() -> None:
    rtype = _prompt(
        f"  Type ({'/'.join(REVIEW_TYPES)}, blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(REVIEW_STATUSES)}, blank): ") or None
    jud = _prompt(f"  Judgement ({'/'.join(JUDGEMENTS)}, blank): ") or None
    rows = data.list_reviews(review_type=rtype, status=status,
                               judgement=jud)
    print(f"\n  {len(rows)} review(s):")
    _print_reviews(rows)
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
    rid = _ask_id("Review ID")
    if rid is None:
        return
    s = data.review_summary(rid)
    r = s["review"]
    print(f"\n  ── Review #{r.review_id} ──")
    print(f"  Title:       {r.title}")
    print(f"  Type / focus: {r.review_type} — {r.focus_area or '-'}")
    print(f"  Lead:        {r.lead_reviewer}    "
          f"Team: {r.additional_team or '-'}")
    print(f"  Date:        {r.review_date}    Status: {r.status}    "
          f"Judgement: {r.judgement}")
    print(f"\n  Strengths:\n    {r.strengths or '-'}")
    print(f"\n  Areas for development:\n    "
          f"{r.areas_for_development or '-'}")
    print(f"\n  Summary:\n    {r.summary or '-'}")
    print(f"\n  Follow-up date: {r.follow_up_date or '-'}")
    print(f"  Notes:       {r.notes or '-'}")
    print(f"\n  Actions: {len(s['actions'])}    Open: "
          f"{s['open_actions']}    Done: {s['done_actions']}    "
          f"Overdue: {s['overdue']}")
    _print_actions(s["actions"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit_review() -> None:
    rid = _ask_id("Review ID")
    if rid is None:
        return
    existing = data.get_review(rid)
    if existing is None:
        print("  No review with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_review(existing)
    r = data.update_review(rid, fields)
    print(f"  Updated review #{r.review_id} (status {r.status})")


@_safe
def _set_status() -> None:
    rid = _ask_id("Review ID")
    if rid is None:
        return
    r = data.get_review(rid)
    if r is None:
        print("  No review with that ID.")
        return
    print(f"  Current: {r.status}    Allowed: "
          f"{', '.join(REVIEW_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    r = data.set_review_status(rid, new)
    print(f"  Status now: {r.status}")


@_safe
def _delete_review() -> None:
    rid = _ask_id("Review ID")
    if rid is None:
        return
    r = data.get_review(rid)
    if r is None:
        print("  No review with that ID.")
        return
    confirm = _prompt(
        f"  Delete review #{rid} '{r.title}' and ALL its actions? "
        f"(y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_review(rid)
    print(f"  Deleted review #{rid}.")


@_safe
def _add_action() -> None:
    rid = _ask_id("Review ID")
    if rid is None:
        return
    if data.get_review(rid) is None:
        print("  No review with that ID.")
        return
    f: dict[str, Any] = {"review_id": rid}
    f["action"]   = _prompt("  Action: ")
    f["owner"]    = _prompt("  Owner: ") or None
    f["due_date"] = _prompt("  Due date (YYYY-MM-DD, blank ok): ") or None
    f["status"]   = _prompt(
        f"  Status ({'/'.join(ACTION_STATUSES)}) [Open]: ") or "Open"
    f["evidence"] = _prompt("  Evidence (required if Done): ") or None
    f["notes"]    = _prompt("  Notes: ") or None
    a = data.add_action(f)
    print(f"  Added action #{a.action_id} (status {a.status})")


@_safe
def _list_actions() -> None:
    rid_raw = _prompt("  Review ID (blank for all): ")
    rid = None
    if rid_raw:
        try:
            rid = int(rid_raw)
        except ValueError:
            print("  Review ID must be a number.")
            return
    status = _prompt(
        f"  Status ({'/'.join(ACTION_STATUSES)}, blank): ") or None
    owner = _prompt("  Owner (blank): ") or None
    overdue = _prompt(
        "  Overdue only? (y/N): ").lower().startswith("y")
    rows = data.list_actions(review_id=rid, status=status,
                               owner=owner, overdue_only=overdue)
    print(f"\n  {len(rows)} action(s):")
    _print_actions(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit_action() -> None:
    aid = _ask_id("Action ID")
    if aid is None:
        return
    existing = data.get_action(aid)
    if existing is None:
        print("  No action with that ID.")
        return

    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")

    f: dict[str, Any] = {}
    f["action"]   = ask("Action", existing.action)
    f["owner"]    = ask("Owner", existing.owner)
    f["due_date"] = ask("Due date", existing.due_date)
    f["status"]   = ask(f"Status ({'/'.join(ACTION_STATUSES)})",
                          existing.status)
    f["evidence"] = ask("Evidence", existing.evidence)
    f["notes"]    = ask("Notes", existing.notes)
    a = data.update_action(aid, f)
    print(f"  Updated action #{a.action_id} (status {a.status})")


@_safe
def _delete_action() -> None:
    aid = _ask_id("Action ID")
    if aid is None:
        return
    a = data.get_action(aid)
    if a is None:
        print("  No action with that ID.")
        return
    confirm = _prompt(f"  Delete action #{aid}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_action(aid)
    print(f"  Deleted action #{aid}.")


@_safe
def _summary() -> None:
    s = data.cohort_summary()
    print(f"\n  Reviews: {s['reviews']}    Actions: {s['actions']}    "
          f"Open: {s['open_actions']}    Overdue: {s['overdue_actions']}")
    print("  By status:    "
          + "   ".join(f"{k}: {v}" for k, v in s["by_status"].items()))
    print("  By judgement: "
          + "   ".join(f"{k}: {v}"
                        for k, v in s["by_judgement"].items()))
    print("  By type:")
    for k, v in sorted(s["by_type"].items(), key=lambda kv: -kv[1]):
        print(f"    {k:<22} {v}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Quality Assurance": open_quality_assurance}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching quality_assurance CLI label: %s", label)
    handler()
    return True
