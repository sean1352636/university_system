"""CLI handlers for first-aid incidents."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.first_aid import (
    first_aid as data,
)
from education_system.primarysch_system.modules.domain.first_aid.first_aid import (
    INJURY_TYPES, SEVERITIES, OUTCOMES,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
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


def _print_table(rows: list[data.Incident]) -> None:
    if not rows:
        print("  (no incidents)")
        return
    print(f"  {'ID':<5} {'Date':<11} {'Time':<6} {'Pupil':<10} "
          f"{'Yr':<3} {'Injury':<22} {'Sev':<10} {'Outcome':<22}")
    print(f"  {'-'*5} {'-'*11} {'-'*6} {'-'*10} {'-'*3} "
          f"{'-'*22} {'-'*10} {'-'*22}")
    for r in rows:
        print(f"  {r.incident_id:<5} {r.incident_date:<11} "
              f"{(r.incident_time or '-'):<6} {r.pupil_id:<10} "
              f"{(r.pupil_year or '-'):<3} "
              f"{r.injury_type[:22]:<22} {r.severity:<10} "
              f"{r.outcome[:22]:<22}")


@_safe
def open_first_aid() -> None:
    logger.debug("CLI: open_first_aid")
    while True:
        print("\n  ── First Aid ──")
        print("   1) New incident")
        print("   2) List incidents")
        print("   3) View incident")
        print("   4) Edit incident")
        print("   5) Summary report")
        print("   6) Delete incident")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new, "2": _list, "3": _view,
            "4": _edit, "5": _summary, "6": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _yn(label: str, current: bool | None = None) -> str:
    sfx = f" [{'y' if current else 'n'}]" if current is not None else ""
    return _prompt(f"  {label}{sfx} (y/n): ")


def _collect(existing: data.Incident | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"]      = ask("Pupil ID",
                                existing.pupil_id if existing else None)
    f["incident_date"] = ask(
        "Date (YYYY-MM-DD, blank = today)",
        existing.incident_date if existing else None)
    f["incident_time"] = ask("Time (HH:MM)",
                                existing.incident_time if existing else None)
    f["location"]      = ask("Location",
                                existing.location if existing else None)
    f["injury_type"]   = ask(
        f"Injury ({'/'.join(INJURY_TYPES)})",
        existing.injury_type if existing else "Bump/Bruise")
    f["severity"]      = ask(
        f"Severity ({'/'.join(SEVERITIES)})",
        existing.severity if existing else "Minor")
    f["body_part"]     = ask("Body part",
                                existing.body_part if existing else None)
    f["description"]   = ask("Description",
                                existing.description if existing else None)
    f["treatment"]     = ask("Treatment given",
                                existing.treatment if existing else None)
    f["treated_by"]    = ask("Treated by",
                                existing.treated_by if existing else None)
    f["outcome"]       = ask(
        f"Outcome ({'/'.join(OUTCOMES)})",
        existing.outcome if existing else "Returned to lesson")
    cur_pc = existing.parent_contacted if existing else False
    pc = _yn("Parent contacted?", cur_pc)
    f["parent_contacted"] = (
        pc.lower() == "y"
        if pc else cur_pc)
    if f["parent_contacted"]:
        f["parent_contact_time"] = ask(
            "Parent contact time (HH:MM)",
            existing.parent_contact_time if existing else None)
    else:
        f["parent_contact_time"] = None
    cur_hr = existing.hospital_referral if existing else False
    hr = _yn("Hospital referral?", cur_hr)
    f["hospital_referral"] = (
        hr.lower() == "y" if hr else cur_hr)
    f["accident_book_ref"] = ask(
        "Accident book ref",
        existing.accident_book_ref if existing else None)
    cur_rr = existing.riddor_reportable if existing else False
    rr = _yn("RIDDOR reportable?", cur_rr)
    f["riddor_reportable"] = (
        rr.lower() == "y" if rr else cur_rr)
    f["follow_up"] = ask("Follow-up",
                           existing.follow_up if existing else None)
    f["notes"]     = ask("Notes",
                           existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── New First-Aid Incident ──")
    fields = _collect()
    if not fields.get("pupil_id"):
        print("  Cancelled.")
        return
    inc = data.create(fields)
    print(f"  Created incident #{inc.incident_id}: {inc.pupil_id} "
          f"{inc.incident_date} — {inc.injury_type} ({inc.severity})")


@_safe
def _list() -> None:
    pid = _prompt("  Pupil ID (blank): ") or None
    frm = _prompt("  From date (blank): ") or None
    to  = _prompt("  To date (blank): ") or None
    sev = _prompt(
        f"  Severity ({'/'.join(SEVERITIES)}, blank): ") or None
    riddor_only = _prompt(
        "  RIDDOR-reportable only? (y/N): ").lower() == "y"
    hospital_only = _prompt(
        "  Hospital referrals only? (y/N): ").lower() == "y"
    rows = data.list_incidents(
        pupil_id=pid, from_date=frm, to_date=to,
        severity=sev, riddor_only=riddor_only,
        hospital_only=hospital_only)
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
    r = data.get(iid)
    if r is None:
        print("  No incident with that ID.")
        return
    print(f"\n  ── Incident #{r.incident_id} ──")
    print(f"  Pupil:        {r.pupil_id} ({r.pupil_name or '-'}, "
          f"Yr {r.pupil_year or '-'})")
    print(f"  When:         {r.incident_date} "
          f"{r.incident_time or '-'}")
    print(f"  Location:     {r.location}")
    print(f"  Injury:       {r.injury_type} "
          f"({r.body_part or '-'})    Severity: {r.severity}")
    print(f"  Description:  {r.description}")
    print(f"  Treatment:    {r.treatment}")
    print(f"  Treated by:   {r.treated_by}")
    print(f"  Outcome:      {r.outcome}")
    print(f"  Parent:       "
          f"{'Yes' if r.parent_contacted else 'No'}"
          f" at {r.parent_contact_time or '-'}")
    print(f"  Hospital ref: "
          f"{'Yes' if r.hospital_referral else 'No'}")
    print(f"  Accident bk:  {r.accident_book_ref or '-'}")
    print(f"  RIDDOR:       "
          f"{'Yes' if r.riddor_reportable else 'No'}")
    print(f"  Follow-up:    {r.follow_up or '-'}")
    print(f"  Notes:        {r.notes or '-'}")
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
    fields = _collect(existing)
    data.update(iid, fields)
    print(f"  Updated incident #{iid}.")


@_safe
def _summary() -> None:
    frm = _prompt("  From date (blank): ") or None
    to  = _prompt("  To date (blank): ") or None
    s = data.cohort_summary(from_date=frm, to_date=to)
    print(f"\n  Total: {s['total']}   Pupils: {s['pupils']}")
    print(f"  Parent contacted: {s['parent_contacted']}   "
          f"Hospital: {s['hospital']}   RIDDOR: {s['riddor']}")
    print("  By severity: "
          + "   ".join(f"{k}: {v}" for k, v in s["by_severity"].items()))
    print("  By injury:   "
          + "   ".join(f"{k}: {v}" for k, v in s["by_injury"].items()))
    print("  By outcome:  "
          + "   ".join(f"{k}: {v}" for k, v in s["by_outcome"].items()))
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    iid = _ask_id("Incident ID")
    if iid is None:
        return
    r = data.get(iid)
    if r is None:
        print("  No incident with that ID.")
        return
    confirm = _prompt(
        f"  Delete incident #{iid} ({r.pupil_id}, "
        f"{r.incident_date}, {r.injury_type})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete(iid):
        print(f"  Deleted incident #{iid}.")


_DISPATCH = {"First Aid": open_first_aid}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching first_aid CLI label: %s", label)
    handler()
    return True
