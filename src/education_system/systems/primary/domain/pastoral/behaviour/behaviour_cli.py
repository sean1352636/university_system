"""CLI handlers for the behaviour log."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.primary.domain.pastoral.behaviour import (
    behaviour as data,
)
from education_system.systems.primary.domain.pastoral.behaviour.behaviour import (
    INCIDENT_TYPES, SEVERITIES, INCIDENT_STATUSES,
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


def _print_table(rows: list[data.Incident]) -> None:
    if not rows:
        print("  (no incidents)")
        return
    print(f"  {'ID':<4} {'Date':<10} {'Time':<5} {'Pupil':<10} "
          f"{'Yr':<3} {'Type':<18} {'Pts':<4} {'Sev':<8} "
          f"{'Status':<10} {'Description':<32}")
    print(f"  {'-'*4} {'-'*10} {'-'*5} {'-'*10} {'-'*3} {'-'*18} "
          f"{'-'*4} {'-'*8} {'-'*10} {'-'*32}")
    for i in rows:
        print(f"  {i.incident_id:<4} {i.incident_date:<10} "
              f"{(i.incident_time or '-'):<5} {i.pupil_id:<10} "
              f"{(i.pupil_year or '-'):<3} "
              f"{i.incident_type[:18]:<18} "
              f"{('+' if i.points > 0 else ''):>1}{i.points:<3} "
              f"{i.severity:<8} {i.status:<10} "
              f"{i.description[:32]:<32}")


@_safe
def open_behaviour() -> None:
    logger.debug("CLI: open_behaviour")
    while True:
        print("\n  ── Behaviour Log ──")
        print("   1) Log incident")
        print("   2) List incidents")
        print("   3) View incident")
        print("   4) Edit incident")
        print("   5) Set status")
        print("   6) Pupil summary")
        print("   7) Cohort summary")
        print("   8) Pupils on -threshold")
        print("   9) Delete incident")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new, "2": _list, "3": _view,
            "4": _edit, "5": _set_status,
            "6": _pupil_summary, "7": _summary,
            "8": _threshold, "9": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.Incident | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"]      = ask("Pupil ID",
                                existing.pupil_id if existing else None)
    f["incident_date"] = ask("Date (YYYY-MM-DD, blank = today)",
                                existing.incident_date if existing
                                else None)
    f["incident_time"] = ask("Time (HH:MM, blank ok)",
                                existing.incident_time if existing
                                else None)
    f["location"]      = ask("Location",
                                existing.location if existing else None)
    f["subject_id"]    = ask("Subject ID (blank ok)",
                                existing.subject_id if existing else None)
    if not existing:
        print("  Incident types:")
        for k, pol in INCIDENT_TYPES.items():
            tag = "+" if pol == "positive" else "-"
            print(f"    [{tag}] {k}")
    f["incident_type"] = ask("Incident type",
                                existing.incident_type if existing
                                else None)
    f["points"]        = ask("Points (signed, blank = ±1)",
                                existing.points if existing else None)
    f["severity"]      = ask(f"Severity ({'/'.join(SEVERITIES)})",
                                existing.severity if existing
                                else "Low")
    f["description"]   = ask("Description",
                                existing.description if existing
                                else None)
    f["raised_by"]     = ask("Raised by",
                                existing.raised_by if existing else None)
    f["action_taken"]  = ask("Action taken",
                                existing.action_taken if existing
                                else None)
    f["status"]        = ask(f"Status ({'/'.join(INCIDENT_STATUSES)})",
                                existing.status if existing else "Open")
    f["notes"]         = ask("Notes",
                                existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── Log Behaviour Incident ──")
    fields = _collect()
    i = data.log_incident(fields)
    print(f"  Logged #{i.incident_id} ({i.incident_type}, "
          f"pts={'+' if i.points > 0 else ''}{i.points}, "
          f"severity={i.severity})")


@_safe
def _list() -> None:
    pid = _prompt("  Pupil ID (blank): ") or None
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    polarity = _prompt("  Polarity (positive/negative, blank): ") or None
    sev = _prompt(f"  Severity ({'/'.join(SEVERITIES)}, blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(INCIDENT_STATUSES)}, blank): ") or None
    df = _prompt("  From date (blank): ") or None
    dt = _prompt("  To date (blank): ") or None
    rows = data.list_incidents(pupil_id=pid, year_group=yg,
                                 polarity=polarity, severity=sev,
                                 status=status, date_from=df,
                                 date_to=dt)
    print(f"\n  {len(rows)} incident(s):")
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
    iid = _ask_id("Incident ID")
    if iid is None:
        return
    i = data.get(iid)
    if i is None:
        print("  No incident with that ID.")
        return
    print(f"\n  ── Incident #{i.incident_id} ──")
    print(f"  Pupil:        {i.pupil_id} ({i.pupil_name or '-'}, "
          f"Yr {i.pupil_year or '-'})")
    print(f"  When:         {i.incident_date} "
          f"{i.incident_time or ''}")
    print(f"  Location:     {i.location or '-'}    "
          f"Subject: {i.subject_code or '-'}")
    print(f"  Type:         {i.incident_type} ({i.polarity})    "
          f"Points: {'+' if i.points > 0 else ''}{i.points}    "
          f"Severity: {i.severity}")
    print(f"  Description:  {i.description}")
    print(f"  Raised by:    {i.raised_by or '-'}")
    print(f"  Action taken: {i.action_taken or '-'}")
    print(f"  Status:       {i.status}")
    print(f"  Notes:        {i.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    iid = _ask_id("Incident ID")
    if iid is None:
        return
    existing = data.get(iid)
    if existing is None:
        print("  No incident with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect(existing)
    i = data.update(iid, fields)
    print(f"  Updated #{i.incident_id} (status {i.status})")


@_safe
def _set_status() -> None:
    iid = _ask_id("Incident ID")
    if iid is None:
        return
    i = data.get(iid)
    if i is None:
        print("  No incident with that ID.")
        return
    print(f"  Current: {i.status}    Allowed: "
          f"{', '.join(INCIDENT_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    i = data.set_status(iid, new)
    print(f"  Status now: {i.status}")


@_safe
def _pupil_summary() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    df = _prompt("  From date (blank): ") or None
    dt = _prompt("  To date (blank): ") or None
    s = data.pupil_summary(pid, date_from=df, date_to=dt)
    print(f"\n  ── {pid} ──")
    print(f"  Total: {s['total']}    Positive: {s['positive']}    "
          f"Negative: {s['negative']}    "
          f"Net points: {'+' if s['total_points'] >= 0 else ''}"
          f"{s['total_points']}")
    if s["by_severity"]:
        print("  By severity: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_severity"].items()))
    if s["by_type"]:
        print("  By type:")
        for k, v in sorted(s["by_type"].items(),
                            key=lambda kv: -kv[1]):
            print(f"    {k:<22} {v}")
    _print_table(s["incidents"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    df = _prompt("  From date (blank): ") or None
    dt = _prompt("  To date (blank): ") or None
    s = data.cohort_summary(year_group=yg, date_from=df, date_to=dt)
    print(f"\n  Total: {s['total']}    Positive: {s['positive']}    "
          f"Negative: {s['negative']}    Open: {s['open']}")
    if s["by_severity"]:
        print("  By severity: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_severity"].items()))
    if s["by_type"]:
        print("  By type:")
        for k, v in sorted(s["by_type"].items(),
                            key=lambda kv: -kv[1])[:10]:
            print(f"    {k:<22} {v}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _threshold() -> None:
    thr = _prompt("  Points-below threshold [-10]: ") or "-10"
    try:
        threshold = int(thr)
    except ValueError:
        print("  Threshold must be an integer.")
        return
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    rows = data.pupils_above_threshold(points_below=threshold,
                                          year_group=yg)
    print(f"\n  {len(rows)} pupil(s) at or below {threshold} points:")
    for pid, pts in rows:
        print(f"    {pid:<12} {pts}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    iid = _ask_id("Incident ID")
    if iid is None:
        return
    i = data.get(iid)
    if i is None:
        print("  No incident with that ID.")
        return
    confirm = _prompt(
        f"  Delete incident #{iid} ({i.pupil_id}, "
        f"{i.incident_type})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete(iid)
    print(f"  Deleted incident #{iid}.")


_DISPATCH = {"Behaviour Log": open_behaviour}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching behaviour CLI label: %s", label)
    handler()
    return True
