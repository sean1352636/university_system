"""CLI handlers for wellbeing check-ins."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.pastoral.wellbeing import (
    wellbeing as data,
)
from education_system.systems.secondary.domain.pastoral.wellbeing.wellbeing import (
    CHECKIN_STATUSES, CHECKIN_SOURCES, MIN_RATING, MAX_RATING,
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


def _print_table(rows: list[data.CheckIn]) -> None:
    if not rows:
        print("  (no check-ins)")
        return
    print(f"  {'ID':<4} {'Date':<10} {'Pupil':<10} {'Yr':<3} "
          f"{'Source':<18} {'Mood':<4} {'Conf':<4} {'Conn':<4} "
          f"{'Avg':<5} {'Action':<6} {'Status':<11}")
    print(f"  {'-'*4} {'-'*10} {'-'*10} {'-'*3} {'-'*18} {'-'*4} "
          f"{'-'*4} {'-'*4} {'-'*5} {'-'*6} {'-'*11}")
    for c in rows:
        avg = (f"{c.average_rating:.2f}"
               if c.average_rating is not None else "-")
        print(f"  {c.checkin_id:<4} {c.checkin_date:<10} "
              f"{c.pupil_id:<10} {(c.pupil_year or '-'):<3} "
              f"{c.source[:18]:<18} "
              f"{(c.mood_rating if c.mood_rating is not None else '-'):<4} "
              f"{(c.confidence_rating if c.confidence_rating is not None else '-'):<4} "
              f"{(c.connection_rating if c.connection_rating is not None else '-'):<4} "
              f"{avg:<5} {('Yes' if c.action_needed else 'No'):<6} "
              f"{c.status:<11}")


@_safe
def open_wellbeing() -> None:
    logger.debug("CLI: open_wellbeing")
    while True:
        print("\n  ── Wellbeing ──")
        print("   1) Log check-in")
        print("   2) List check-ins")
        print("   3) View check-in")
        print("   4) Edit check-in")
        print("   5) Set status")
        print("   6) Pupil summary")
        print("   7) Cohort summary")
        print("   8) Pupils with low ratings")
        print("   9) Delete check-in")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new, "2": _list, "3": _view, "4": _edit,
            "5": _set_status, "6": _pupil_summary,
            "7": _summary, "8": _low, "9": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.CheckIn | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"]      = ask("Pupil ID",
                                existing.pupil_id if existing else None)
    f["checkin_date"]  = ask("Date (YYYY-MM-DD, blank = today)",
                                existing.checkin_date if existing
                                else None)
    f["source"]        = ask(f"Source ({'/'.join(CHECKIN_SOURCES)})",
                                existing.source if existing
                                else "Form tutor")
    f["mood_rating"]   = ask(
        f"Mood ({MIN_RATING}-{MAX_RATING}, blank ok)",
        existing.mood_rating if existing else None)
    f["confidence_rating"] = ask(
        f"Confidence ({MIN_RATING}-{MAX_RATING}, blank ok)",
        existing.confidence_rating if existing else None)
    f["connection_rating"] = ask(
        f"Connection ({MIN_RATING}-{MAX_RATING}, blank ok)",
        existing.connection_rating if existing else None)
    f["stressors"]     = ask("Stressors",
                                existing.stressors if existing else None)
    f["supports"]      = ask("Supports",
                                existing.supports if existing else None)
    act = ask("Action needed? (y/n)",
                "y" if existing and existing.action_needed else "n")
    f["action_needed"] = act.lower().startswith("y")
    f["action_summary"] = ask(
        "Action summary (required if action_needed)",
        existing.action_summary if existing else None)
    f["recorded_by"]   = ask("Recorded by",
                                existing.recorded_by if existing
                                else None)
    f["status"]        = ask(f"Status ({'/'.join(CHECKIN_STATUSES)})",
                                existing.status if existing else "Open")
    f["follow_up_date"] = ask("Follow-up date (YYYY-MM-DD, blank ok)",
                                  existing.follow_up_date if existing
                                  else None)
    f["follow_up_with"] = ask("Follow-up with",
                                  existing.follow_up_with if existing
                                  else None)
    f["notes"]         = ask("Notes",
                                existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── Log Wellbeing Check-in ──")
    fields = _collect()
    c = data.log_checkin(fields)
    print(f"  Logged #{c.checkin_id} for {c.pupil_id} "
          f"(avg={c.average_rating}, action_needed={c.action_needed})")


@_safe
def _list() -> None:
    pid = _prompt("  Pupil ID (blank): ") or None
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(CHECKIN_STATUSES)}, blank): ") or None
    src = _prompt(f"  Source ({'/'.join(CHECKIN_SOURCES)}, blank): ") or None
    act = _prompt("  Action needed only? (y/N): ")
    action_needed = True if act.lower().startswith("y") else None
    df = _prompt("  From date (blank): ") or None
    dt = _prompt("  To date (blank): ") or None
    rows = data.list_checkins(pupil_id=pid, year_group=yg,
                                status=status, source=src,
                                action_needed=action_needed,
                                date_from=df, date_to=dt)
    print(f"\n  {len(rows)} check-in(s):")
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
    cid = _ask_id("Check-in ID")
    if cid is None:
        return
    c = data.get(cid)
    if c is None:
        print("  No check-in with that ID.")
        return
    print(f"\n  ── Check-in #{c.checkin_id} ──")
    print(f"  Pupil:        {c.pupil_id} ({c.pupil_name or '-'}, "
          f"Yr {c.pupil_year or '-'})")
    print(f"  Date:         {c.checkin_date}    Source: {c.source}")
    print(f"  Mood:         {c.mood_rating or '-'}    "
          f"Confidence: {c.confidence_rating or '-'}    "
          f"Connection: {c.connection_rating or '-'}    "
          f"Avg: {c.average_rating if c.average_rating is not None else '-'}")
    print(f"  Stressors:    {c.stressors or '-'}")
    print(f"  Supports:     {c.supports or '-'}")
    print(f"  Action needed: "
          f"{'Yes' if c.action_needed else 'No'}    "
          f"Summary: {c.action_summary or '-'}")
    print(f"  Recorded by:  {c.recorded_by or '-'}")
    print(f"  Status:       {c.status}")
    print(f"  Follow-up:    {c.follow_up_date or '-'} "
          f"with {c.follow_up_with or '-'}")
    print(f"  Notes:        {c.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    cid = _ask_id("Check-in ID")
    if cid is None:
        return
    existing = data.get(cid)
    if existing is None:
        print("  No check-in with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect(existing)
    c = data.update(cid, fields)
    print(f"  Updated check-in #{c.checkin_id} (status {c.status})")


@_safe
def _set_status() -> None:
    cid = _ask_id("Check-in ID")
    if cid is None:
        return
    c = data.get(cid)
    if c is None:
        print("  No check-in with that ID.")
        return
    print(f"  Current: {c.status}    Allowed: "
          f"{', '.join(CHECKIN_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    c = data.set_status(cid, new)
    print(f"  Status now: {c.status}")


@_safe
def _pupil_summary() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    s = data.pupil_summary(pid)
    print(f"\n  ── {pid} ──")
    print(f"  Check-ins: {s['count']}    "
          f"Action needed: {s['action_needed']}")
    print(f"  Avg mood: "
          f"{s['avg_mood'] if s['avg_mood'] is not None else '-'}    "
          f"Avg confidence: "
          f"{s['avg_confidence'] if s['avg_confidence'] is not None else '-'}    "
          f"Avg connection: "
          f"{s['avg_connection'] if s['avg_connection'] is not None else '-'}")
    if s["by_status"]:
        print("  By status: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    _print_table(s["checkins"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    df = _prompt("  From date (blank): ") or None
    dt = _prompt("  To date (blank): ") or None
    s = data.cohort_summary(year_group=yg, date_from=df, date_to=dt)
    print(f"\n  Total: {s['total']}    "
          f"Action needed: {s['action_needed']}")
    print(f"  Avg mood: "
          f"{s['avg_mood'] if s['avg_mood'] is not None else '-'}    "
          f"Avg confidence: "
          f"{s['avg_confidence'] if s['avg_confidence'] is not None else '-'}    "
          f"Avg connection: "
          f"{s['avg_connection'] if s['avg_connection'] is not None else '-'}")
    if s["by_status"]:
        print("  By status: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    if s["by_source"]:
        print("  By source: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_source"].items()))
    _prompt("\n  Press Enter to continue...")


@_safe
def _low() -> None:
    thr = _prompt(f"  Threshold ({MIN_RATING}-{MAX_RATING}) [2]: ") or "2"
    try:
        t = int(thr)
    except ValueError:
        print("  Threshold must be an integer.")
        return
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    pupils = data.low_wellbeing(threshold=t, year_group=yg)
    print(f"\n  {len(pupils)} pupil(s) with latest rating ≤ {t}:")
    for pid, checkins in pupils.items():
        c = checkins[0]
        print(f"    {pid:<12}  {c.checkin_date}  "
              f"mood={c.mood_rating or '-'} "
              f"conf={c.confidence_rating or '-'} "
              f"conn={c.connection_rating or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    cid = _ask_id("Check-in ID")
    if cid is None:
        return
    c = data.get(cid)
    if c is None:
        print("  No check-in with that ID.")
        return
    confirm = _prompt(
        f"  Delete check-in #{cid} ({c.pupil_id}, {c.checkin_date})? "
        f"(y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete(cid)
    print(f"  Deleted check-in #{cid}.")


_DISPATCH = {"Wellbeing": open_wellbeing}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching wellbeing CLI label: %s", label)
    handler()
    return True
