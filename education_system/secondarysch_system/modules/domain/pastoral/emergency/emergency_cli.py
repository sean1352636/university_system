"""CLI handlers for emergency events and drills."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.pastoral.emergency import (
    emergency as data,
)
from education_system.secondarysch_system.modules.domain.pastoral.emergency.emergency import (
    EVENT_KINDS, EMERGENCY_TYPES, OUTCOMES, STATUSES,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
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


def _print_table(rows: list[data.Event]) -> None:
    if not rows:
        print("  (no events)")
        return
    print(f"  {'ID':<5} {'Date':<11} {'Kind':<10} "
          f"{'Type':<16} {'Dur':<5} {'Pups':<5} {'Mis':<4} "
          f"{'Inj':<4} {'Outcome':<20} {'Status':<20}")
    print(f"  {'-'*5} {'-'*11} {'-'*10} {'-'*16} {'-'*5} {'-'*5} "
          f"{'-'*4} {'-'*4} {'-'*20} {'-'*20}")
    for r in rows:
        dur = str(r.duration_min) if r.duration_min is not None else "-"
        pups = str(r.pupils_evacuated) if r.pupils_evacuated is not None else "-"
        print(f"  {r.event_id:<5} {r.event_date:<11} "
              f"{r.kind:<10} {r.event_type[:16]:<16} {dur:<5} "
              f"{pups:<5} {r.missing_count:<4} "
              f"{r.injuries_count:<4} {r.outcome[:20]:<20} "
              f"{r.status[:20]:<20}")


@_safe
def open_emergency() -> None:
    logger.debug("CLI: open_emergency")
    while True:
        print("\n  ── Emergency & Drills ──")
        print("   1) New event")
        print("   2) List events")
        print("   3) View event")
        print("   4) Edit event")
        print("   5) Set status")
        print("   6) Close event")
        print("   7) Summary report")
        print("   8) Delete event")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new, "2": _list, "3": _view, "4": _edit,
            "5": _set_status, "6": _close, "7": _summary,
            "8": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.Event | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")

    f: dict[str, Any] = {}
    f["kind"]       = ask(f"Kind ({'/'.join(EVENT_KINDS)})",
                            existing.kind if existing else "Drill")
    f["event_type"] = ask(
        f"Type ({'/'.join(EMERGENCY_TYPES)})",
        existing.event_type if existing else "Fire")
    f["event_date"] = ask(
        "Date (YYYY-MM-DD, blank = today)",
        existing.event_date if existing else None)
    f["start_time"] = ask("Start time (HH:MM)",
                            existing.start_time if existing else None)
    f["end_time"]   = ask("End time (HH:MM)",
                            existing.end_time if existing else None)
    f["duration_min"] = ask(
        "Duration min (blank to auto)",
        existing.duration_min if existing else None)
    f["location"]   = ask("Location",
                            existing.location if existing else None)
    f["trigger"]    = ask("Trigger / cause",
                            existing.trigger if existing else None)
    f["reported_by"] = ask("Reported by",
                             existing.reported_by if existing else None)
    f["incident_commander"] = ask(
        "Incident commander",
        existing.incident_commander if existing else None)
    f["pupils_evacuated"] = ask(
        "Pupils evacuated",
        existing.pupils_evacuated if existing else None)
    f["staff_evacuated"] = ask(
        "Staff evacuated",
        existing.staff_evacuated if existing else None)
    f["missing_count"] = ask(
        "Missing count",
        existing.missing_count if existing else 0)
    f["injuries_count"] = ask(
        "Injuries count",
        existing.injuries_count if existing else 0)
    es_cur = existing.emergency_services if existing else False
    es = _prompt(
        f"  Emergency services? [{'y' if es_cur else 'n'}] (y/n): ")
    f["emergency_services"] = (
        es.lower() == "y" if es else es_cur)
    f["services_attended"] = ask(
        "Services attended (Fire/Police/Ambulance)",
        existing.services_attended if existing else None)
    f["outcome"]   = ask(
        f"Outcome ({'/'.join(OUTCOMES)})",
        existing.outcome if existing else "Successful")
    f["status"]    = ask(
        f"Status ({'/'.join(STATUSES)})",
        existing.status if existing else "Logged")
    f["lessons_learned"]   = ask(
        "Lessons learned",
        existing.lessons_learned if existing else None)
    f["follow_up_actions"] = ask(
        "Follow-up actions",
        existing.follow_up_actions if existing else None)
    f["notes"]     = ask("Notes",
                           existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── New Emergency / Drill ──")
    fields = _collect()
    if not fields.get("event_type"):
        print("  Cancelled.")
        return
    r = data.create(fields)
    print(f"  Created event #{r.event_id}: {r.kind} {r.event_type} "
          f"on {r.event_date} ({r.outcome}, {r.status})")


@_safe
def _list() -> None:
    kind = _prompt(
        f"  Kind ({'/'.join(EVENT_KINDS)}, blank): ") or None
    etype = _prompt(
        f"  Type ({'/'.join(EMERGENCY_TYPES)}, blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(STATUSES)}, blank): ") or None
    frm = _prompt("  From date (blank): ") or None
    to  = _prompt("  To date (blank): ") or None
    outstanding = _prompt(
        "  Outstanding only? (y/N): ").lower() == "y"
    rows = data.list_events(
        kind=kind, event_type=etype, status=status,
        from_date=frm, to_date=to,
        outstanding_only=outstanding)
    print(f"\n  {len(rows)} event(s):")
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
    eid = _ask_id("Event ID")
    if eid is None:
        return
    r = data.get(eid)
    if r is None:
        print("  No event with that ID.")
        return
    print(f"\n  ── Event #{r.event_id} ──")
    print(f"  Kind/type:    {r.kind} / {r.event_type}")
    print(f"  When:         {r.event_date}  "
          f"{r.start_time or '-'} → {r.end_time or '-'}    "
          f"({r.duration_min if r.duration_min is not None else '-'} "
          f"min)")
    print(f"  Location:     {r.location or '-'}")
    print(f"  Trigger:      {r.trigger or '-'}")
    print(f"  Reported by:  {r.reported_by or '-'}")
    print(f"  Commander:    {r.incident_commander or '-'}")
    print(f"  Pupils evac:  "
          f"{r.pupils_evacuated if r.pupils_evacuated is not None else '-'}")
    print(f"  Staff evac:   "
          f"{r.staff_evacuated if r.staff_evacuated is not None else '-'}")
    print(f"  Missing:      {r.missing_count}    "
          f"Injuries: {r.injuries_count}")
    print(f"  Services:     "
          f"{'Yes' if r.emergency_services else 'No'}    "
          f"{r.services_attended or '-'}")
    print(f"  Outcome:      {r.outcome}")
    print(f"  Status:       {r.status}")
    print(f"  Lessons:      {r.lessons_learned or '-'}")
    print(f"  Follow-up:    {r.follow_up_actions or '-'}")
    print(f"  Notes:        {r.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    eid = _ask_id("Event ID")
    if eid is None:
        return
    existing = data.get(eid)
    if existing is None:
        print("  No event with that ID.")
        return
    fields = _collect(existing)
    data.update(eid, fields)
    print(f"  Updated event #{eid}.")


@_safe
def _set_status() -> None:
    eid = _ask_id("Event ID")
    if eid is None:
        return
    r = data.get(eid)
    if r is None:
        print("  No event with that ID.")
        return
    print(f"  Current: {r.status}")
    print(f"  Allowed: {', '.join(STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    r = data.set_status(eid, new)
    print(f"  Status now: {r.status}")


@_safe
def _close() -> None:
    eid = _ask_id("Event ID")
    if eid is None:
        return
    r = data.close_event(eid)
    print(f"  Closed event #{r.event_id}.")


@_safe
def _summary() -> None:
    frm = _prompt("  From date (blank): ") or None
    to  = _prompt("  To date (blank): ") or None
    s = data.cohort_summary(from_date=frm, to_date=to)
    print(f"\n  Total: {s['total']}   Drills: {s['drills']}   "
          f"Real: {s['real']}   Outstanding: {s['outstanding']}")
    avg = s["avg_duration_min"]
    print(f"  Avg duration: "
          f"{f'{avg:.1f}' if avg is not None else '-'} min")
    print(f"  Missing total: {s['total_missing']}   "
          f"Injuries total: {s['total_injuries']}   "
          f"Services called: {s['services_called']}")
    print(f"  By type:    "
          + "   ".join(f"{k}: {v}" for k, v in s["by_type"].items()))
    print(f"  By outcome: "
          + "   ".join(f"{k}: {v}" for k, v in s["by_outcome"].items()))
    print(f"  By status:  "
          + "   ".join(f"{k}: {v}" for k, v in s["by_status"].items()))
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    eid = _ask_id("Event ID")
    if eid is None:
        return
    r = data.get(eid)
    if r is None:
        print("  No event with that ID.")
        return
    confirm = _prompt(
        f"  Delete event #{eid} ({r.kind} {r.event_type}, "
        f"{r.event_date})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete(eid):
        print(f"  Deleted event #{eid}.")


_DISPATCH = {"Emergency": open_emergency}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching emergency CLI label: %s", label)
    handler()
    return True
