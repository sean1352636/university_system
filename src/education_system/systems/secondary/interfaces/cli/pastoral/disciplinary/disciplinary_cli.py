"""CLI handlers for disciplinary cases."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.pastoral.disciplinary import (
    disciplinary as data,
)
from education_system.systems.secondary.domain.pastoral.disciplinary.disciplinary import (
    CASE_TYPES, CASE_STATUSES, SEVERITIES, EVENT_TYPES,
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


def _print_cases(rows: list[data.DisciplinaryCase]) -> None:
    if not rows:
        print("  (no cases)")
        return
    print(f"  {'ID':<4} {'Start':<10} {'Pupil':<10} {'Yr':<3} "
          f"{'Type':<22} {'Sev':<9} {'Days':<4} {'Status':<11} "
          f"{'Reason':<28}")
    print(f"  {'-'*4} {'-'*10} {'-'*10} {'-'*3} {'-'*22} {'-'*9} "
          f"{'-'*4} {'-'*11} {'-'*28}")
    for c in rows:
        print(f"  {c.case_id:<4} {c.start_date:<10} {c.pupil_id:<10} "
              f"{(c.pupil_year or '-'):<3} "
              f"{c.case_type[:22]:<22} {c.severity:<9} "
              f"{(str(c.days) if c.days is not None else '-'):<4} "
              f"{c.status:<11} {c.reason[:28]:<28}")


def _print_events(rows: list[data.DisciplinaryEvent]) -> None:
    if not rows:
        print("  (no events)")
        return
    print(f"  {'ID':<5} {'Date':<10} {'Type':<20} "
          f"{'Participants':<24} {'Summary':<36}")
    print(f"  {'-'*5} {'-'*10} {'-'*20} {'-'*24} {'-'*36}")
    for e in rows:
        print(f"  {e.event_id:<5} {e.event_date:<10} "
              f"{e.event_type[:20]:<20} "
              f"{(e.participants or '-')[:24]:<24} "
              f"{e.summary[:36]:<36}")


@_safe
def open_disciplinary() -> None:
    logger.debug("CLI: open_disciplinary")
    while True:
        print("\n  ── Disciplinary ──")
        print("  Cases")
        print("    1) New case")
        print("    2) List cases")
        print("    3) View case + events")
        print("    4) Edit case")
        print("    5) Set status")
        print("    6) Delete case")
        print("  Events")
        print("    7) Add event")
        print("    8) Delete event")
        print("  Reports")
        print("    9) Cohort summary")
        print("    0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new_case, "2": _list_cases, "3": _view,
            "4": _edit_case, "5": _set_status,
            "6": _delete_case,
            "7": _add_event, "8": _delete_event,
            "9": _summary,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect_case(existing: data.DisciplinaryCase | None = None
                   ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"]       = ask("Pupil ID",
                                  existing.pupil_id if existing else None)
    f["case_type"]      = ask(f"Type ({'/'.join(CASE_TYPES)})",
                                  existing.case_type if existing
                                  else "Fixed-term suspension")
    f["severity"]       = ask(f"Severity ({'/'.join(SEVERITIES)})",
                                  existing.severity if existing
                                  else "High")
    f["incident_date"]  = ask("Incident date (YYYY-MM-DD, blank ok)",
                                  existing.incident_date if existing
                                  else None)
    f["start_date"]     = ask("Start date (YYYY-MM-DD)",
                                  existing.start_date if existing
                                  else None)
    f["end_date"]       = ask("End date (YYYY-MM-DD, blank ok)",
                                  existing.end_date if existing
                                  else None)
    f["days"]           = ask("Days (blank = auto)",
                                  existing.days if existing else None)
    f["reason"]         = ask("Reason",
                                  existing.reason if existing else None)
    f["decision_maker"] = ask("Decision maker",
                                  existing.decision_maker if existing
                                  else None)
    f["status"]         = ask(f"Status ({'/'.join(CASE_STATUSES)})",
                                  existing.status if existing else "Open")
    f["appeal_decision"] = ask(
        "Appeal decision (required if Appealed/Overturned)",
        existing.appeal_decision if existing else None)
    f["return_date"]    = ask("Return date (YYYY-MM-DD, blank ok)",
                                  existing.return_date if existing
                                  else None)
    f["notes"]          = ask("Notes",
                                  existing.notes if existing else None)
    return f


@_safe
def _new_case() -> None:
    print("\n  ── New Disciplinary Case ──")
    fields = _collect_case()
    c = data.create_case(fields)
    print(f"  Created case #{c.case_id}: {c.pupil_id} — "
          f"{c.case_type} ({c.severity}, {c.days or '?'} days)")


@_safe
def _list_cases() -> None:
    pid = _prompt("  Pupil ID (blank): ") or None
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    ctype = _prompt(f"  Type ({'/'.join(CASE_TYPES)}, blank): ") or None
    sev = _prompt(f"  Severity ({'/'.join(SEVERITIES)}, blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(CASE_STATUSES)}, blank): ") or None
    df = _prompt("  From date (blank): ") or None
    dt = _prompt("  To date (blank): ") or None
    rows = data.list_cases(pupil_id=pid, year_group=yg,
                              case_type=ctype, severity=sev,
                              status=status,
                              date_from=df, date_to=dt)
    print(f"\n  {len(rows)} case(s):")
    _print_cases(rows)
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
    cid = _ask_id("Case ID")
    if cid is None:
        return
    s = data.case_summary(cid)
    c = s["case"]
    print(f"\n  ── Case #{c.case_id} ──")
    print(f"  Pupil:        {c.pupil_id} ({c.pupil_name or '-'}, "
          f"Yr {c.pupil_year or '-'})")
    print(f"  Type:         {c.case_type}    "
          f"Severity: {c.severity}")
    print(f"  Incident:     {c.incident_date or '-'}")
    print(f"  Start / end:  {c.start_date} → {c.end_date or '-'}    "
          f"({c.days or '?'} days)")
    print(f"  Reason:       {c.reason}")
    print(f"  Decision:     {c.decision_maker or '-'}")
    print(f"  Status:       {c.status}    "
          f"Appeal: {c.appeal_decision or '-'}")
    print(f"  Return date:  {c.return_date or '-'}")
    print(f"  Notes:        {c.notes or '-'}")
    print(f"\n  Events: {s['event_count']}")
    if s["by_type"]:
        print("  By type: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_type"].items()))
    _print_events(s["events"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit_case() -> None:
    cid = _ask_id("Case ID")
    if cid is None:
        return
    existing = data.get_case(cid)
    if existing is None:
        print("  No case with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_case(existing)
    c = data.update_case(cid, fields)
    print(f"  Updated case #{c.case_id} (status {c.status})")


@_safe
def _set_status() -> None:
    cid = _ask_id("Case ID")
    if cid is None:
        return
    c = data.get_case(cid)
    if c is None:
        print("  No case with that ID.")
        return
    print(f"  Current: {c.status}    Allowed: "
          f"{', '.join(CASE_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    appeal = None
    if new in ("Appealed", "Overturned"):
        appeal = _prompt("  Appeal decision: ")
        if not appeal:
            print("  Appeal decision required.")
            return
    c = data.set_status(cid, new, appeal_decision=appeal)
    print(f"  Status now: {c.status}")


@_safe
def _delete_case() -> None:
    cid = _ask_id("Case ID")
    if cid is None:
        return
    c = data.get_case(cid)
    if c is None:
        print("  No case with that ID.")
        return
    confirm = _prompt(
        f"  Delete case #{cid} ({c.pupil_id}, {c.case_type}) and ALL "
        f"its events? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_case(cid)
    print(f"  Deleted case #{cid}.")


@_safe
def _add_event() -> None:
    cid = _ask_id("Case ID")
    if cid is None:
        return
    if data.get_case(cid) is None:
        print("  No case with that ID.")
        return
    f: dict[str, Any] = {"case_id": cid}
    f["event_date"] = _prompt(
        "  Event date (YYYY-MM-DD, blank = today): ") or None
    f["event_type"] = _prompt(
        f"  Type ({'/'.join(EVENT_TYPES)}) [Meeting]: ") or "Meeting"
    f["participants"] = _prompt("  Participants: ") or None
    f["summary"] = _prompt("  Summary: ")
    f["outcome"] = _prompt("  Outcome: ") or None
    f["follow_up"] = _prompt("  Follow-up: ") or None
    f["notes"] = _prompt("  Notes: ") or None
    e = data.add_event(f)
    print(f"  Added event #{e.event_id} ({e.event_type})")


@_safe
def _delete_event() -> None:
    eid = _ask_id("Event ID")
    if eid is None:
        return
    e = data.get_event(eid)
    if e is None:
        print("  No event with that ID.")
        return
    confirm = _prompt(
        f"  Delete event #{eid} (case #{e.case_id})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_event(eid)
    print(f"  Deleted event #{eid}.")


@_safe
def _summary() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    df = _prompt("  From date (blank): ") or None
    dt = _prompt("  To date (blank): ") or None
    s = data.cohort_summary(year_group=yg, date_from=df, date_to=dt)
    print(f"\n  Cases: {s['total']}    Open: {s['open']}    "
          f"Total days: {s['total_days']}")
    if s["by_status"]:
        print("  By status:   "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    if s["by_severity"]:
        print("  By severity: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_severity"].items()))
    if s["by_type"]:
        print("  By type:")
        for k, v in sorted(s["by_type"].items(), key=lambda kv: -kv[1]):
            print(f"    {k:<26} {v}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Disciplinary": open_disciplinary}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching disciplinary CLI label: %s", label)
    handler()
    return True
