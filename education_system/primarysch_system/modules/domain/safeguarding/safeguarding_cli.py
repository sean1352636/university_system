"""CLI handlers for safeguarding."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.safeguarding import (
    safeguarding as data,
)
from education_system.primarysch_system.modules.domain.safeguarding.safeguarding import (
    CONCERN_CATEGORIES, SEVERITIES, CONCERN_STATUSES,
    REFERRAL_BODIES, ACTION_TYPES,
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


def _print_concerns(rows: list[data.Concern], *,
                     show_description: bool = False) -> None:
    if not rows:
        print("  (no concerns)")
        return
    print(f"  {'ID':<4} {'Raised':<10} {'Pupil':<10} {'Yr':<3} "
          f"{'Category':<22} {'Sev':<9} {'Status':<11} "
          f"{'DSL':<16} {'Conf':<5}")
    print(f"  {'-'*4} {'-'*10} {'-'*10} {'-'*3} {'-'*22} {'-'*9} "
          f"{'-'*11} {'-'*16} {'-'*5}")
    for c in rows:
        print(f"  {c.concern_id:<4} {c.raised_date:<10} "
              f"{c.pupil_id:<10} {(c.pupil_year or '-'):<3} "
              f"{c.category[:22]:<22} {c.severity:<9} "
              f"{c.status:<11} "
              f"{(c.dsl_reviewer or '-')[:16]:<16} "
              f"{('Y' if c.confidential else 'N'):<5}")
        if show_description and not c.confidential:
            print(f"        {c.description[:100]}")


def _print_actions(rows: list[data.SGAction]) -> None:
    if not rows:
        print("  (no actions)")
        return
    print(f"  {'ID':<5} {'Date':<10} {'Type':<24} {'By':<18} "
          f"{'Summary':<40}")
    print(f"  {'-'*5} {'-'*10} {'-'*24} {'-'*18} {'-'*40}")
    for a in rows:
        print(f"  {a.action_id:<5} {a.action_date:<10} "
              f"{a.action_type[:24]:<24} "
              f"{(a.actioned_by or '-')[:18]:<18} "
              f"{a.summary[:40]:<40}")


@_safe
def open_safeguarding() -> None:
    logger.debug("CLI: open_safeguarding")
    while True:
        print("\n  ── Safeguarding ──")
        print("  Concerns")
        print("    1) Raise concern")
        print("    2) List concerns")
        print("    3) View concern + actions")
        print("    4) Edit concern")
        print("    5) Set status")
        print("    6) Pupils with open concerns (≥ High)")
        print("    7) Delete concern")
        print("  Actions")
        print("    8) Add action")
        print("    9) Delete action")
        print("  Reports")
        print("   10) Cohort summary")
        print("    0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new, "2": _list, "3": _view,
            "4": _edit, "5": _set_status,
            "6": _at_risk, "7": _delete,
            "8": _add_action, "9": _delete_action,
            "10": _summary,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect_concern(existing: data.Concern | None = None
                      ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"]    = ask("Pupil ID",
                                existing.pupil_id if existing else None)
    if not existing:
        print("  Categories:")
        for c in CONCERN_CATEGORIES:
            print(f"    • {c}")
    f["category"]    = ask("Category",
                                existing.category if existing
                                else "Disclosure")
    f["severity"]    = ask(f"Severity ({'/'.join(SEVERITIES)})",
                                existing.severity if existing
                                else "Medium")
    f["incident_date"] = ask("Incident date (YYYY-MM-DD, blank ok)",
                                  existing.incident_date if existing
                                  else None)
    f["incident_time"] = ask("Incident time (HH:MM, blank ok)",
                                  existing.incident_time if existing
                                  else None)
    f["location"]    = ask("Location",
                                existing.location if existing else None)
    f["description"] = ask("Description (required)",
                                existing.description if existing
                                else None)
    f["raised_by"]   = ask("Raised by",
                                existing.raised_by if existing else None)
    f["raised_date"] = ask("Raised date (YYYY-MM-DD, blank = today)",
                                existing.raised_date if existing
                                else None)
    f["dsl_reviewer"] = ask("DSL reviewer",
                                 existing.dsl_reviewer if existing
                                 else None)
    f["review_date"] = ask("DSL review date (blank ok)",
                                existing.review_date if existing
                                else None)
    f["status"]      = ask(f"Status ({'/'.join(CONCERN_STATUSES)})",
                                existing.status if existing else "Open")
    f["referral_body"] = ask(
        f"Referral body ({'/'.join(REFERRAL_BODIES)}, blank ok)",
        existing.referral_body if existing else None)
    f["referral_date"] = ask("Referral date (blank ok)",
                                  existing.referral_date if existing
                                  else None)
    f["referral_reference"] = ask(
        "Referral reference (blank ok)",
        existing.referral_reference if existing else None)
    f["outcome"]     = ask("Outcome",
                                existing.outcome if existing else None)
    f["closed_date"] = ask("Closed date (blank ok)",
                                existing.closed_date if existing
                                else None)
    conf = ask("Confidential? (y/n)",
                "y" if (existing is None or existing.confidential)
                else "n")
    f["confidential"] = conf.lower().startswith("y")
    f["notes"]       = ask("Notes",
                                existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── Raise Safeguarding Concern ──")
    fields = _collect_concern()
    c = data.raise_concern(fields)
    print(f"  Raised concern #{c.concern_id}: {c.category} "
          f"({c.severity}, {c.status})")


@_safe
def _list() -> None:
    pid = _prompt("  Pupil ID (blank): ") or None
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    cat = _prompt("  Category (blank): ") or None
    sev = _prompt(f"  Severity ({'/'.join(SEVERITIES)}, blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(CONCERN_STATUSES)}, blank): ") or None
    df = _prompt("  From date (blank): ") or None
    dt = _prompt("  To date (blank): ") or None
    show_desc = _prompt(
        "  Show description? (y/N): ").lower().startswith("y")
    rows = data.list_concerns(pupil_id=pid, year_group=yg,
                                category=cat, severity=sev,
                                status=status, date_from=df,
                                date_to=dt)
    print(f"\n  {len(rows)} concern(s):")
    _print_concerns(rows, show_description=show_desc)
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
    cid = _ask_id("Concern ID")
    if cid is None:
        return
    s = data.concern_summary(cid)
    c = s["concern"]
    print(f"\n  ── Concern #{c.concern_id} ──")
    print(f"  Pupil:        {c.pupil_id} ({c.pupil_name or '-'}, "
          f"Yr {c.pupil_year or '-'})")
    print(f"  Category:     {c.category}    "
          f"Severity: {c.severity}")
    print(f"  Incident:     {c.incident_date or '-'} "
          f"{c.incident_time or ''}    "
          f"Location: {c.location or '-'}")
    print(f"  Raised by:    {c.raised_by or '-'}    "
          f"on {c.raised_date}")
    print(f"  DSL:          {c.dsl_reviewer or '-'}    "
          f"review {c.review_date or '-'}")
    print(f"  Status:       {c.status}")
    print(f"  Referral:     {c.referral_body or '-'}    "
          f"on {c.referral_date or '-'}    "
          f"ref: {c.referral_reference or '-'}")
    print(f"  Outcome:      {c.outcome or '-'}")
    print(f"  Closed:       {c.closed_date or '-'}")
    print(f"  Confidential: {'Yes' if c.confidential else 'No'}")
    print(f"\n  Description:\n    {c.description}")
    print(f"\n  Notes:\n    {c.notes or '-'}")
    print(f"\n  Actions: {s['action_count']}")
    if s["by_type"]:
        print("  By type:")
        for k, v in s["by_type"].items():
            print(f"    {k:<26} {v}")
    _print_actions(s["actions"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    cid = _ask_id("Concern ID")
    if cid is None:
        return
    existing = data.get(cid)
    if existing is None:
        print("  No concern with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_concern(existing)
    c = data.update(cid, fields)
    print(f"  Updated concern #{c.concern_id} (status {c.status})")


@_safe
def _set_status() -> None:
    cid = _ask_id("Concern ID")
    if cid is None:
        return
    c = data.get(cid)
    if c is None:
        print("  No concern with that ID.")
        return
    print(f"  Current: {c.status}    Allowed: "
          f"{', '.join(CONCERN_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    outcome = None
    referral = None
    if new == "Closed":
        outcome = _prompt("  Outcome: ")
        if not outcome:
            print("  Outcome required for Closed.")
            return
    if new == "Referred":
        referral = _prompt(
            f"  Referral body ({'/'.join(REFERRAL_BODIES)}): ")
        if not referral:
            print("  Referral body required for Referred.")
            return
    c = data.set_status(cid, new, outcome=outcome,
                          referral_body=referral)
    print(f"  Status now: {c.status}")


@_safe
def _at_risk() -> None:
    sev = _prompt(
        f"  Minimum severity ({'/'.join(SEVERITIES)}) [High]: "
    ) or "High"
    pupils = data.pupils_with_concerns(severity_min=sev)
    print(f"\n  {len(pupils)} pupil(s) with open concerns ≥ {sev}:")
    for pid, concerns in pupils.items():
        print(f"\n  Pupil {pid} — {len(concerns)} concern(s):")
        for c in concerns:
            print(f"    #{c.concern_id:<5} {c.severity:<8} "
                  f"{c.category[:24]:<24} {c.status}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    cid = _ask_id("Concern ID")
    if cid is None:
        return
    c = data.get(cid)
    if c is None:
        print("  No concern with that ID.")
        return
    confirm = _prompt(
        f"  Delete concern #{cid} ({c.pupil_id}, {c.category}) "
        f"and ALL its actions? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete(cid)
    print(f"  Deleted concern #{cid}.")


@_safe
def _add_action() -> None:
    cid = _ask_id("Concern ID")
    if cid is None:
        return
    if data.get(cid) is None:
        print("  No concern with that ID.")
        return
    f: dict[str, Any] = {"concern_id": cid}
    f["action_date"] = _prompt(
        "  Action date (YYYY-MM-DD, blank = today): ") or None
    f["action_type"] = _prompt(
        f"  Type ({'/'.join(ACTION_TYPES)}) [DSL meeting]: "
    ) or "DSL meeting"
    f["actioned_by"] = _prompt("  Actioned by: ") or None
    f["summary"]     = _prompt("  Summary: ")
    f["outcome"]     = _prompt("  Outcome: ") or None
    f["follow_up"]   = _prompt("  Follow-up: ") or None
    a = data.add_action(f)
    print(f"  Added action #{a.action_id} ({a.action_type})")


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
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    df = _prompt("  From date (blank): ") or None
    dt = _prompt("  To date (blank): ") or None
    s = data.cohort_summary(year_group=yg, date_from=df, date_to=dt)
    print(f"\n  Concerns: {s['total']}    Open: {s['open']}    "
          f"Open Critical: {s['open_critical']}")
    if s["by_severity"]:
        print("  By severity: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_severity"].items()))
    if s["by_status"]:
        print("  By status:   "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    if s["by_category"]:
        print("  By category:")
        for k, v in sorted(s["by_category"].items(),
                            key=lambda kv: -kv[1]):
            print(f"    {k:<32} {v}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Safeguarding": open_safeguarding}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching safeguarding CLI label: %s", label)
    handler()
    return True
