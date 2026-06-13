"""CLI handlers for detentions."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.pastoral.detentions import (
    detentions as data,
)
from education_system.secondarysch_system.modules.domain.pastoral.detentions.detentions import (
    DETENTION_TYPES, DETENTION_STATUSES,
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


def _print_table(rows: list[data.Detention]) -> None:
    if not rows:
        print("  (no detentions)")
        return
    print(f"  {'ID':<4} {'Date':<10} {'Time':<5} {'Pupil':<10} "
          f"{'Yr':<3} {'Type':<14} {'Dur':<4} {'Supervisor':<18} "
          f"{'Status':<11} {'Reason':<28}")
    print(f"  {'-'*4} {'-'*10} {'-'*5} {'-'*10} {'-'*3} {'-'*14} "
          f"{'-'*4} {'-'*18} {'-'*11} {'-'*28}")
    for d in rows:
        print(f"  {d.detention_id:<4} {d.detention_date:<10} "
              f"{(d.start_time or '-'):<5} {d.pupil_id:<10} "
              f"{(d.pupil_year or '-'):<3} "
              f"{d.detention_type[:14]:<14} {d.duration_min:<4} "
              f"{(d.supervisor or '-')[:18]:<18} {d.status:<11} "
              f"{d.reason[:28]:<28}")


@_safe
def open_detentions() -> None:
    logger.debug("CLI: open_detentions")
    while True:
        print("\n  ── Detentions ──")
        print("   1) Schedule detention")
        print("   2) List detentions")
        print("   3) View detention")
        print("   4) Edit detention")
        print("   5) Mark attended / missed / excused")
        print("   6) Reschedule")
        print("   7) Daily register")
        print("   8) Pupil summary")
        print("   9) Cohort summary")
        print("  10) Delete detention")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new, "2": _list, "3": _view,
            "4": _edit, "5": _set_status,
            "6": _reschedule, "7": _register,
            "8": _pupil_summary, "9": _summary, "10": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.Detention | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"]       = ask("Pupil ID",
                                  existing.pupil_id if existing else None)
    f["detention_date"] = ask("Date (YYYY-MM-DD)",
                                  existing.detention_date if existing
                                  else None)
    f["start_time"]     = ask("Start time (HH:MM, blank ok)",
                                  existing.start_time if existing
                                  else None)
    f["duration_min"]   = ask("Duration in minutes",
                                  existing.duration_min if existing
                                  else 30)
    f["detention_type"] = ask(f"Type ({'/'.join(DETENTION_TYPES)})",
                                  existing.detention_type if existing
                                  else "After school")
    f["location"]       = ask("Location",
                                  existing.location if existing else None)
    f["supervisor"]     = ask("Supervisor",
                                  existing.supervisor if existing
                                  else None)
    f["reason"]         = ask("Reason",
                                  existing.reason if existing else None)
    f["set_by"]         = ask("Set by",
                                  existing.set_by if existing else None)
    f["status"]         = ask(
        f"Status ({'/'.join(DETENTION_STATUSES)})",
        existing.status if existing else "Scheduled")
    f["related_incident_id"] = ask(
        "Related incident ID (blank ok)",
        existing.related_incident_id if existing else None)
    f["notes"]          = ask("Notes",
                                  existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── Schedule Detention ──")
    fields = _collect()
    d = data.create(fields)
    print(f"  Scheduled #{d.detention_id} for {d.pupil_id} on "
          f"{d.detention_date} ({d.detention_type}, "
          f"{d.duration_min}min)")


@_safe
def _list() -> None:
    pid = _prompt("  Pupil ID (blank): ") or None
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(DETENTION_STATUSES)}, blank): ") or None
    dtype = _prompt(
        f"  Type ({'/'.join(DETENTION_TYPES)}, blank): ") or None
    df = _prompt("  From date (blank): ") or None
    dt = _prompt("  To date (blank): ") or None
    rows = data.list_detentions(pupil_id=pid, year_group=yg,
                                  status=status,
                                  detention_type=dtype,
                                  date_from=df, date_to=dt)
    print(f"\n  {len(rows)} detention(s):")
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
    did = _ask_id("Detention ID")
    if did is None:
        return
    d = data.get(did)
    if d is None:
        print("  No detention with that ID.")
        return
    print(f"\n  ── Detention #{d.detention_id} ──")
    print(f"  Pupil:       {d.pupil_id} ({d.pupil_name or '-'}, "
          f"Yr {d.pupil_year or '-'})")
    print(f"  When:        {d.detention_date} "
          f"{d.start_time or ''}    {d.duration_min} min")
    print(f"  Type:        {d.detention_type}")
    print(f"  Location:    {d.location or '-'}")
    print(f"  Supervisor:  {d.supervisor or '-'}")
    print(f"  Set by:      {d.set_by or '-'}")
    print(f"  Status:      {d.status}")
    print(f"  Reason:      {d.reason}")
    print(f"  Incident:    "
          f"#{d.related_incident_id}" if d.related_incident_id
          else "  Incident:    -")
    if d.rescheduled_to:
        print(f"  Rescheduled to: #{d.rescheduled_to}")
    print(f"  Notes:       {d.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    did = _ask_id("Detention ID")
    if did is None:
        return
    existing = data.get(did)
    if existing is None:
        print("  No detention with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect(existing)
    d = data.update(did, fields)
    print(f"  Updated detention #{d.detention_id} (status {d.status})")


@_safe
def _set_status() -> None:
    did = _ask_id("Detention ID")
    if did is None:
        return
    d = data.get(did)
    if d is None:
        print("  No detention with that ID.")
        return
    print(f"  Current: {d.status}    Allowed: "
          f"{', '.join(DETENTION_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    d = data.set_status(did, new)
    print(f"  Status now: {d.status}")


@_safe
def _reschedule() -> None:
    did = _ask_id("Detention ID to reschedule")
    if did is None:
        return
    new_date = _prompt("  New date (YYYY-MM-DD): ")
    if not new_date:
        return
    new_time = _prompt("  New start time (HH:MM, blank to keep): ") or None
    new_loc  = _prompt("  New location (blank to keep): ") or None
    new_sup  = _prompt("  New supervisor (blank to keep): ") or None
    notes    = _prompt("  Notes (blank ok): ") or None
    new = data.reschedule(did, new_date=new_date,
                            new_start_time=new_time,
                            new_location=new_loc,
                            new_supervisor=new_sup,
                            notes=notes)
    print(f"  Rescheduled #{did} → new detention "
          f"#{new.detention_id} on {new.detention_date}")


@_safe
def _register() -> None:
    date_s = _prompt("  Date (YYYY-MM-DD): ")
    if not date_s:
        return
    dtype = _prompt(
        f"  Type filter ({'/'.join(DETENTION_TYPES)}, blank): ") or None
    rows = data.daily_register(date_s, detention_type=dtype)
    print(f"\n  Daily register for {date_s}: {len(rows)} detention(s)")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _pupil_summary() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    s = data.pupil_summary(pid)
    print(f"\n  ── Detentions for {pid} ──")
    print(f"  Total: {s['total']}    Attended: {s['attended']}    "
          f"Missed: {s['missed']}    Excused: {s['excused']}    "
          f"Scheduled: {s['scheduled']}")
    print(f"  Minutes served: {s['minutes_served']}")
    _print_table(s["detentions"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    df = _prompt("  From date (blank): ") or None
    dt = _prompt("  To date (blank): ") or None
    s = data.cohort_summary(year_group=yg, date_from=df, date_to=dt)
    print(f"\n  Total: {s['total']}    Attended: {s['attended']}    "
          f"Missed: {s['missed']}    "
          f"Minutes served: {s['minutes_served']}")
    if s["by_status"]:
        print("  By status: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    if s["by_type"]:
        print("  By type:   "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_type"].items()))
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    did = _ask_id("Detention ID")
    if did is None:
        return
    d = data.get(did)
    if d is None:
        print("  No detention with that ID.")
        return
    confirm = _prompt(
        f"  Delete detention #{did} ({d.pupil_id}, "
        f"{d.detention_date})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete(did)
    print(f"  Deleted detention #{did}.")


_DISPATCH = {"Detentions": open_detentions}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching detentions CLI label: %s", label)
    handler()
    return True
