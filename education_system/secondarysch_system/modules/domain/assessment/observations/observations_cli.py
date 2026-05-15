"""CLI handlers for lesson observations."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.assessment.observations import (
    observations as data,
)
from education_system.secondarysch_system.modules.domain.assessment.observations.observations import (
    OBSERVATION_TYPES, JUDGEMENTS, OBSERVATION_STATUSES,
    MIN_PERIOD, MAX_PERIOD,
)
from education_system.secondarysch_system.modules.domain.academics.subjects import (
    subjects as subjects_data,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
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


def _print_table(rows: list[data.Observation]) -> None:
    if not rows:
        print("  (no observations)")
        return
    print(f"  {'ID':<4} {'Date':<10} {'P':<2} {'Teacher':<18} "
          f"{'Subj':<6} {'Yr':<3} {'Observer':<18} "
          f"{'Type':<14} {'Judgement':<20} {'Status':<10}")
    print(f"  {'-'*4} {'-'*10} {'-'*2} {'-'*18} {'-'*6} {'-'*3} "
          f"{'-'*18} {'-'*14} {'-'*20} {'-'*10}")
    for o in rows:
        print(f"  {o.observation_id:<4} {o.observation_date:<10} "
              f"{(str(o.period) if o.period else '-'):<2} "
              f"{o.teacher[:18]:<18} "
              f"{(o.subject_code or '-'):<6} "
              f"{(o.year_group or '-'):<3} "
              f"{o.observer[:18]:<18} "
              f"{o.observation_type[:14]:<14} "
              f"{o.judgement[:20]:<20} {o.status:<10}")


@_safe
def open_observations() -> None:
    logger.debug("CLI: open_observations")
    while True:
        print("\n  ── Observations ──")
        print("   1) New observation")
        print("   2) List observations")
        print("   3) View observation")
        print("   4) Edit observation")
        print("   5) Set status")
        print("   6) Teacher summary")
        print("   7) Cohort summary")
        print("   8) Delete observation")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new, "2": _list, "3": _view,
            "4": _edit, "5": _set_status,
            "6": _teacher_summary, "7": _summary, "8": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.Observation | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["teacher"] = ask("Teacher",
                         existing.teacher if existing else None)
    if not existing:
        print("  Active subjects (optional):")
        for s in subjects_data.list_all(active_only=True)[:20]:
            print(f"    #{s.subject_id:<4} {s.code:<8} {s.name}")
    f["subject_id"] = ask("Subject ID (blank ok)",
                            existing.subject_id if existing else None)
    f["year_group"] = ask(f"Year ({'/'.join(YEAR_GROUPS)}, blank ok)",
                            existing.year_group if existing else None)
    f["form_group"] = ask("Form (blank ok)",
                            existing.form_group if existing else None)
    f["observation_date"] = ask(
        "Date (YYYY-MM-DD, blank = today)",
        existing.observation_date if existing else None)
    f["period"]   = ask(f"Period ({MIN_PERIOD}-{MAX_PERIOD}, blank ok)",
                          existing.period if existing else None)
    f["observer"] = ask("Observer",
                          existing.observer if existing else None)
    f["observation_type"] = ask(
        f"Type ({'/'.join(OBSERVATION_TYPES)})",
        existing.observation_type if existing else "Learning walk")
    f["focus"]    = ask("Focus",
                          existing.focus if existing else None)
    f["judgement"] = ask(f"Judgement ({'/'.join(JUDGEMENTS)})",
                           existing.judgement if existing
                           else "Not judged")
    f["strengths"]         = ask("Strengths",
                                    existing.strengths if existing
                                    else None)
    f["development_areas"] = ask("Development areas",
                                    existing.development_areas if existing
                                    else None)
    f["action_points"]     = ask("Action points",
                                    existing.action_points if existing
                                    else None)
    f["follow_up_date"]    = ask(
        "Follow-up date (YYYY-MM-DD, blank ok)",
        existing.follow_up_date if existing else None)
    f["status"]   = ask(f"Status ({'/'.join(OBSERVATION_STATUSES)})",
                          existing.status if existing else "Scheduled")
    f["notes"]    = ask("Notes",
                          existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── New Observation ──")
    fields = _collect()
    o = data.create(fields)
    print(f"  Created observation #{o.observation_id} for "
          f"{o.teacher} on {o.observation_date} "
          f"({o.observation_type}, {o.status})")


@_safe
def _list() -> None:
    teacher = _prompt("  Teacher (blank): ") or None
    observer = _prompt("  Observer (blank): ") or None
    otype = _prompt(
        f"  Type ({'/'.join(OBSERVATION_TYPES)}, blank): ") or None
    jud = _prompt(f"  Judgement ({'/'.join(JUDGEMENTS)}, blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(OBSERVATION_STATUSES)}, blank): ") or None
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    rows = data.list_observations(teacher=teacher, observer=observer,
                                    observation_type=otype,
                                    judgement=jud, status=status,
                                    year_group=yg)
    print(f"\n  {len(rows)} observation(s):")
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
    oid = _ask_id("Observation ID")
    if oid is None:
        return
    o = data.get(oid)
    if o is None:
        print("  No observation with that ID.")
        return
    print(f"\n  ── Observation #{o.observation_id} ──")
    print(f"  Teacher:       {o.teacher}")
    print(f"  Subject:       {o.subject_code or '-'} "
          f"{('— ' + o.subject_name) if o.subject_name else ''}")
    print(f"  Year/form:     {o.year_group or '-'}"
          f"{('/' + o.form_group) if o.form_group else ''}")
    print(f"  Date/period:   {o.observation_date}    "
          f"P{o.period or '-'}")
    print(f"  Observer:      {o.observer}")
    print(f"  Type:          {o.observation_type}    "
          f"Judgement: {o.judgement}    Status: {o.status}")
    print(f"  Focus:         {o.focus or '-'}")
    print(f"\n  Strengths:\n    {o.strengths or '-'}")
    print(f"\n  Development areas:\n    {o.development_areas or '-'}")
    print(f"\n  Action points:\n    {o.action_points or '-'}")
    print(f"\n  Follow-up date: {o.follow_up_date or '-'}")
    print(f"  Notes:         {o.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    oid = _ask_id("Observation ID")
    if oid is None:
        return
    existing = data.get(oid)
    if existing is None:
        print("  No observation with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect(existing)
    o = data.update(oid, fields)
    print(f"  Updated #{o.observation_id} "
          f"(judgement {o.judgement}, status {o.status})")


@_safe
def _set_status() -> None:
    oid = _ask_id("Observation ID")
    if oid is None:
        return
    o = data.get(oid)
    if o is None:
        print("  No observation with that ID.")
        return
    print(f"  Current: {o.status}")
    print(f"  Allowed: {', '.join(OBSERVATION_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    o = data.set_status(oid, new)
    print(f"  Status now: {o.status}")


@_safe
def _teacher_summary() -> None:
    teacher = _prompt("  Teacher name: ")
    if not teacher:
        return
    s = data.teacher_summary(teacher)
    print(f"\n  Observations for {teacher}: {s['total']}")
    if s["by_judgement"]:
        print("  By judgement: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_judgement"].items()))
    if s["by_type"]:
        print("  By type:      "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_type"].items()))
    if s["by_status"]:
        print("  By status:    "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    _print_table(s["observations"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    s = data.cohort_summary()
    print(f"\n  Total observations: {s['total']}    "
          f"Follow-ups due: {s['follow_ups']}")
    if s["by_judgement"]:
        print("  By judgement: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_judgement"].items()))
    if s["by_type"]:
        print("  By type:      "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_type"].items()))
    if s["by_status"]:
        print("  By status:    "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    oid = _ask_id("Observation ID")
    if oid is None:
        return
    o = data.get(oid)
    if o is None:
        print("  No observation with that ID.")
        return
    confirm = _prompt(
        f"  Delete observation #{oid} ({o.teacher} on "
        f"{o.observation_date})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete(oid)
    print(f"  Deleted observation #{oid}.")


_DISPATCH = {"Observations": open_observations}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching observations CLI label: %s", label)
    handler()
    return True
