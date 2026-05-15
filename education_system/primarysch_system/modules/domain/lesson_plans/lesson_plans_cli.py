"""CLI handlers for lesson plans."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.lesson_plans import (
    lesson_plans as data,
)
from education_system.primarysch_system.modules.domain.lesson_plans.lesson_plans import (
    STATUSES, MIN_PERIOD, MAX_PERIOD,
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


def _print_table(rows: list[data.LessonPlan]) -> None:
    if not rows:
        print("  (no lesson plans)")
        return
    print(f"  {'ID':<5} {'Date':<10} {'P':<3} {'Yr':<3} {'Form':<5} "
          f"{'Subj':<8} {'Title':<28} {'Teacher':<16} {'Status':<10}")
    print(f"  {'-'*5} {'-'*10} {'-'*3} {'-'*3} {'-'*5} {'-'*8} {'-'*28} "
          f"{'-'*16} {'-'*10}")
    for p in rows:
        print(f"  {p.plan_id:<5} {p.planned_date:<10} "
              f"{(str(p.period) if p.period else '-'):<3} "
              f"{p.year_group:<3} {(p.form_group or '-'):<5} "
              f"{(p.subject_code or '?'):<8} {p.title[:28]:<28} "
              f"{(p.teacher or '-')[:16]:<16} {p.status:<10}")


def _print_detail(p: data.LessonPlan) -> None:
    print(f"\n  ── Lesson plan #{p.plan_id} ──")
    print(f"  Title:        {p.title}")
    print(f"  Subject:      {p.subject_code} — {p.subject_name}")
    print(f"  Year/form:    {p.year_group}"
          f"{('/' + p.form_group) if p.form_group else ''}")
    print(f"  Date/period:  {p.planned_date}  "
          f"P{p.period or '-'}  ({p.duration_min or '?'} min)")
    print(f"  Teacher:      {p.teacher or '-'}")
    print(f"  Status:       {p.status}")
    print(f"\n  Objectives:\n    {p.objectives or '-'}")
    print(f"\n  Activities:\n    {p.activities or '-'}")
    print(f"\n  Resources:\n    {p.resources or '-'}")
    print(f"\n  Differentiation:\n    {p.differentiation or '-'}")
    print(f"\n  Assessment:\n    {p.assessment or '-'}")
    print(f"\n  Homework:\n    {p.homework or '-'}")
    print(f"\n  Notes:\n    {p.notes or '-'}")


@_safe
def open_lesson_plans() -> None:
    logger.debug("CLI: open_lesson_plans")
    while True:
        counts = data.status_counts()
        total = sum(counts.values())
        print("\n  ── Lesson Plans ──")
        print(f"  Total: {total}   "
              + "   ".join(f"{s}: {counts[s]}" for s in STATUSES))
        print("\n   1) New plan")
        print("   2) List plans")
        print("   3) View plan")
        print("   4) Edit plan")
        print("   5) Set status")
        print("   6) Delete plan")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new,
            "2": _list,
            "3": _view,
            "4": _edit,
            "5": _set_status,
            "6": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.LessonPlan | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")

    f: dict[str, Any] = {}
    f["title"] = ask("Title", existing.title if existing else None)
    if not existing:
        print("  Active subjects:")
        for s in subjects_data.list_all(active_only=True):
            print(f"    #{s.subject_id:<4} {s.code:<8} {s.name}")
    f["subject_id"]      = ask("Subject ID",
                                existing.subject_id if existing else None)
    f["year_group"]      = ask(f"Year ({'/'.join(YEAR_GROUPS)})",
                                existing.year_group if existing else None)
    f["form_group"]      = ask("Form (blank = whole year)",
                                existing.form_group if existing else None)
    f["planned_date"]    = ask("Date (YYYY-MM-DD)",
                                existing.planned_date if existing else None)
    f["period"]          = ask(f"Period ({MIN_PERIOD}-{MAX_PERIOD}, blank ok)",
                                existing.period if existing else None)
    f["duration_min"]    = ask("Duration in minutes",
                                existing.duration_min if existing else 60)
    f["teacher"]         = ask("Teacher",
                                existing.teacher if existing else None)
    f["status"]          = ask(f"Status ({'/'.join(STATUSES)})",
                                existing.status if existing else "Draft")
    f["objectives"]      = ask("Objectives",
                                existing.objectives if existing else None)
    f["activities"]      = ask("Activities",
                                existing.activities if existing else None)
    f["resources"]       = ask("Resources",
                                existing.resources if existing else None)
    f["differentiation"] = ask("Differentiation",
                                existing.differentiation if existing else None)
    f["assessment"]      = ask("Assessment",
                                existing.assessment if existing else None)
    f["homework"]        = ask("Homework",
                                existing.homework if existing else None)
    f["notes"]           = ask("Notes",
                                existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── New Lesson Plan ──")
    fields = _collect()
    p = data.create(fields)
    print(f"  Created plan #{p.plan_id}: {p.title}")


@_safe
def _list() -> None:
    print(f"\n  Filter — year ({'/'.join(YEAR_GROUPS)}), blank for all.")
    yg = _prompt("  Year: ") or None
    sid_raw = _prompt("  Subject ID (blank for all): ")
    subject_id = None
    if sid_raw:
        try:
            subject_id = int(sid_raw)
        except ValueError:
            print("  Subject ID must be a number.")
            return
    teacher = _prompt("  Teacher (blank for all): ") or None
    print(f"  Status ({'/'.join(STATUSES)}) or blank.")
    status = _prompt("  Status: ") or None
    date_from = _prompt("  From date (YYYY-MM-DD, blank): ") or None
    date_to = _prompt("  To date (YYYY-MM-DD, blank): ") or None
    rows = data.list_plans(year_group=yg, subject_id=subject_id,
                           teacher=teacher, status=status,
                           date_from=date_from, date_to=date_to)
    print(f"\n  {len(rows)} plan(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_id() -> int | None:
    pid = _prompt("  Plan ID: ")
    if not pid:
        return None
    try:
        return int(pid)
    except ValueError:
        print("  Plan ID must be a number.")
        return None


@_safe
def _view() -> None:
    plan_id = _ask_id()
    if plan_id is None:
        return
    p = data.get(plan_id)
    if p is None:
        print("  No plan with that ID.")
        return
    _print_detail(p)
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    plan_id = _ask_id()
    if plan_id is None:
        return
    existing = data.get(plan_id)
    if existing is None:
        print("  No plan with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect(existing)
    p = data.update(plan_id, fields)
    print(f"  Updated plan #{p.plan_id} (status {p.status})")


@_safe
def _set_status() -> None:
    plan_id = _ask_id()
    if plan_id is None:
        return
    p = data.get(plan_id)
    if p is None:
        print("  No plan with that ID.")
        return
    print(f"  Current status: {p.status}")
    print(f"  Allowed: {', '.join(STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    p = data.set_status(plan_id, new)
    print(f"  Status now: {p.status}")


@_safe
def _delete() -> None:
    plan_id = _ask_id()
    if plan_id is None:
        return
    p = data.get(plan_id)
    if p is None:
        print("  No plan with that ID.")
        return
    confirm = _prompt(
        f"  Delete plan #{plan_id} ({p.title})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete(plan_id):
        print(f"  Deleted plan #{plan_id}.")
    else:
        print("  Could not delete.")


_DISPATCH = {"Lesson Plans": open_lesson_plans}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching lesson_plans CLI label: %s", label)
    handler()
    return True
