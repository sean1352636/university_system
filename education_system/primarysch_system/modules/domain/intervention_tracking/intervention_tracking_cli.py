"""CLI handlers for intervention tracking."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.intervention_tracking import (
    intervention_tracking as data,
)
from education_system.primarysch_system.modules.domain.intervention_tracking.intervention_tracking import (
    INTERVENTION_TYPES, INTERVENTION_STATUSES, FREQUENCIES, OUTCOMES,
)
from education_system.primarysch_system.modules.domain.subjects import (
    subjects as subjects_data,
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


def _print_table(rows: list[data.Intervention]) -> None:
    if not rows:
        print("  (no interventions)")
        return
    print(f"  {'ID':<4} {'Pupil':<10} {'Yr':<3} {'Subj':<6} "
          f"{'Type':<14} {'Start':<10} {'Led by':<14} "
          f"{'Freq':<10} {'Status':<10} {'Outcome':<10}")
    print(f"  {'-'*4} {'-'*10} {'-'*3} {'-'*6} {'-'*14} {'-'*10} "
          f"{'-'*14} {'-'*10} {'-'*10} {'-'*10}")
    for i in rows:
        print(f"  {i.intervention_id:<4} {i.pupil_id:<10} "
              f"{(i.pupil_year or '-'):<3} "
              f"{(i.subject_code or '-'):<6} "
              f"{i.intervention_type[:14]:<14} {i.start_date:<10} "
              f"{(i.led_by or '-')[:14]:<14} "
              f"{i.frequency[:10]:<10} {i.status:<10} "
              f"{(i.outcome or '-')[:10]:<10}")


def _print_reviews(rows: list[data.InterventionReview]) -> None:
    if not rows:
        print("  (no reviews)")
        return
    print(f"  {'ID':<5} {'Date':<10} {'Reviewer':<18} {'Att%':<6} "
          f"{'OnTrk':<5} {'Notes':<28} {'Next':<24}")
    print(f"  {'-'*5} {'-'*10} {'-'*18} {'-'*6} {'-'*5} {'-'*28} "
          f"{'-'*24}")
    for r in rows:
        print(f"  {r.review_id:<5} {r.review_date:<10} "
              f"{(r.reviewer or '-')[:18]:<18} "
              f"{(f'{r.attendance_pct:.0f}' if r.attendance_pct is not None else '-'):<6} "
              f"{('Y' if r.on_track else 'N'):<5} "
              f"{(r.progress_notes or '-')[:28]:<28} "
              f"{(r.next_action or '-')[:24]:<24}")


@_safe
def open_intervention_tracking() -> None:
    logger.debug("CLI: open_intervention_tracking")
    while True:
        print("\n  ── Intervention Tracking ──")
        print("  Interventions")
        print("    1) New intervention")
        print("    2) List interventions")
        print("    3) View intervention + reviews")
        print("    4) Edit intervention")
        print("    5) Set status (with outcome)")
        print("    6) Delete intervention")
        print("  Reviews")
        print("    7) Add review")
        print("    8) Delete review")
        print("  Reports")
        print("    9) Cohort summary")
        print("    0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new, "2": _list, "3": _view,
            "4": _edit, "5": _set_status, "6": _delete,
            "7": _add_review, "8": _delete_review,
            "9": _summary,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.Intervention | None = None
              ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"] = ask("Pupil ID",
                         existing.pupil_id if existing else None)
    if not existing:
        print("  Active subjects (optional):")
        for s in subjects_data.list_all(active_only=True)[:20]:
            print(f"    #{s.subject_id:<4} {s.code:<8} {s.name}")
    f["subject_id"] = ask("Subject ID (blank ok)",
                           existing.subject_id if existing else None)
    f["intervention_type"] = ask(
        f"Type ({'/'.join(INTERVENTION_TYPES)})",
        existing.intervention_type if existing else "Catch-up")
    f["goal"]       = ask("Goal",
                            existing.goal if existing else None)
    f["start_date"] = ask("Start date (YYYY-MM-DD, blank = today)",
                            existing.start_date if existing else None)
    f["end_date"]   = ask("End date (blank ok)",
                            existing.end_date if existing else None)
    f["status"]     = ask(f"Status ({'/'.join(INTERVENTION_STATUSES)})",
                            existing.status if existing else "Planned")
    f["led_by"]     = ask("Led by",
                            existing.led_by if existing else None)
    f["location"]   = ask("Location",
                            existing.location if existing else None)
    f["frequency"]  = ask(f"Frequency ({'/'.join(FREQUENCIES)})",
                            existing.frequency if existing else "Weekly")
    f["baseline_grade"] = ask("Baseline grade",
                                existing.baseline_grade if existing
                                else None)
    f["target_grade"]   = ask("Target grade",
                                existing.target_grade if existing
                                else None)
    f["current_grade"]  = ask("Current grade",
                                existing.current_grade if existing
                                else None)
    f["outcome"]    = ask(f"Outcome ({'/'.join(OUTCOMES)}, blank ok)",
                            existing.outcome if existing else None)
    f["notes"]      = ask("Notes",
                            existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── New Intervention ──")
    fields = _collect()
    i = data.create(fields)
    print(f"  Created intervention #{i.intervention_id} for "
          f"{i.pupil_id} ({i.intervention_type})")


@_safe
def _list() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(INTERVENTION_STATUSES)}, blank): ") or None
    itype = _prompt(
        f"  Type ({'/'.join(INTERVENTION_TYPES)}, blank): ") or None
    pid = _prompt("  Pupil ID (blank): ") or None
    rows = data.list_interventions(year_group=yg, status=status,
                                     intervention_type=itype,
                                     pupil_id=pid)
    print(f"\n  {len(rows)} intervention(s):")
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
    iid = _ask_id("Intervention ID")
    if iid is None:
        return
    s = data.intervention_summary(iid)
    i = s["intervention"]
    print(f"\n  ── Intervention #{i.intervention_id} ──")
    print(f"  Pupil:    {i.pupil_id} ({i.pupil_name or '-'}, "
          f"Yr {i.pupil_year or '-'})")
    print(f"  Subject:  {i.subject_code or '-'} "
          f"{('— ' + i.subject_name) if i.subject_name else ''}")
    print(f"  Type:     {i.intervention_type}    "
          f"Status: {i.status}    Outcome: {i.outcome or '-'}")
    print(f"  Goal:     {i.goal or '-'}")
    print(f"  Start:    {i.start_date}    End: {i.end_date or '-'}    "
          f"Freq: {i.frequency}")
    print(f"  Led by:   {i.led_by or '-'}    "
          f"Location: {i.location or '-'}")
    print(f"  Grades:   baseline={i.baseline_grade or '-'}   "
          f"target={i.target_grade or '-'}   "
          f"current={i.current_grade or '-'}")
    print(f"  Notes:    {i.notes or '-'}")
    print(f"\n  Reviews: {s['review_count']}    "
          f"Avg att%: "
          f"{s['avg_attendance'] if s['avg_attendance'] is not None else '-'}    "
          f"On-track: {s['on_track']}    "
          f"Off-track: {s['off_track']}")
    _print_reviews(s["reviews"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    iid = _ask_id("Intervention ID")
    if iid is None:
        return
    existing = data.get(iid)
    if existing is None:
        print("  No intervention with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect(existing)
    rec = data.update(iid, fields)
    print(f"  Updated intervention #{rec.intervention_id} "
          f"(status {rec.status})")


@_safe
def _set_status() -> None:
    iid = _ask_id("Intervention ID")
    if iid is None:
        return
    existing = data.get(iid)
    if existing is None:
        print("  No intervention with that ID.")
        return
    print(f"  Current: {existing.status}    "
          f"Outcome: {existing.outcome or '-'}")
    print(f"  Allowed status: {', '.join(INTERVENTION_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    outcome = None
    if new in ("Complete", "Cancelled"):
        print(f"  Outcome ({'/'.join(OUTCOMES)}):")
        outcome = _prompt("  Outcome: ") or None
    rec = data.set_status(iid, new, outcome=outcome)
    print(f"  Status now: {rec.status}    "
          f"Outcome: {rec.outcome or '-'}")


@_safe
def _delete() -> None:
    iid = _ask_id("Intervention ID")
    if iid is None:
        return
    i = data.get(iid)
    if i is None:
        print("  No intervention with that ID.")
        return
    confirm = _prompt(
        f"  Delete intervention #{iid} ({i.pupil_id}, "
        f"{i.intervention_type}) and all its reviews? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete(iid)
    print(f"  Deleted intervention #{iid}.")


@_safe
def _add_review() -> None:
    iid = _ask_id("Intervention ID")
    if iid is None:
        return
    if data.get(iid) is None:
        print("  No intervention with that ID.")
        return
    f: dict[str, Any] = {"intervention_id": iid}
    f["review_date"] = _prompt(
        "  Review date (YYYY-MM-DD, blank = today): ") or None
    f["reviewer"]    = _prompt("  Reviewer: ") or None
    f["attendance_pct"] = _prompt(
        "  Attendance % (0-100, blank ok): ") or None
    f["on_track"]    = not _prompt(
        "  Off-track? (y/N): ").lower().startswith("y")
    f["progress_notes"] = _prompt("  Progress notes: ") or None
    f["next_action"]    = _prompt("  Next action: ") or None
    r = data.add_review(f)
    print(f"  Added review #{r.review_id} (on_track={r.on_track}).")


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
        f"  Delete review #{rid} (intervention #{r.intervention_id})? "
        f"(y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_review(rid)
    print(f"  Deleted review #{rid}.")


@_safe
def _summary() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    s = data.cohort_summary(year_group=yg)
    print(f"\n  Total interventions: {s['total']}")
    if s["by_status"]:
        print("  By status: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    if s["by_type"]:
        print("  By type:")
        for k, v in sorted(s["by_type"].items(),
                            key=lambda kv: -kv[1]):
            print(f"    {k:<18} {v}")
    if s["by_outcome"]:
        print("  By outcome: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_outcome"].items()))
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Intervention Tracking": open_intervention_tracking}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching intervention_tracking CLI label: %s",
                 label)
    handler()
    return True
