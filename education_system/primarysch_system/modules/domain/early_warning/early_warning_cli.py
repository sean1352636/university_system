"""CLI handlers for early-warning alerts."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.early_warning import (
    early_warning as data,
)
from education_system.primarysch_system.modules.domain.early_warning.early_warning import (
    ALERT_TYPES, SEVERITIES, ALERT_STATUSES, SOURCES,
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


def _print_table(rows: list[data.Alert]) -> None:
    if not rows:
        print("  (no alerts)")
        return
    print(f"  {'ID':<4} {'Raised':<10} {'Pupil':<10} {'Yr':<3} "
          f"{'Type':<18} {'Severity':<9} {'Status':<12} "
          f"{'Source':<14} {'Title':<28}")
    print(f"  {'-'*4} {'-'*10} {'-'*3} {'-'*10} {'-'*18} {'-'*9} "
          f"{'-'*12} {'-'*14} {'-'*28}")
    for a in rows:
        print(f"  {a.alert_id:<4} {a.raised_date:<10} {a.pupil_id:<10} "
              f"{(a.pupil_year or '-'):<3} "
              f"{a.alert_type[:18]:<18} {a.severity:<9} "
              f"{a.status:<12} {a.source[:14]:<14} "
              f"{a.title[:28]:<28}")


@_safe
def open_early_warning() -> None:
    logger.debug("CLI: open_early_warning")
    while True:
        print("\n  ── Early Warning ──")
        print("   1) Raise new alert")
        print("   2) List alerts")
        print("   3) View alert")
        print("   4) Edit alert")
        print("   5) Set alert status")
        print("   6) Resolve alert")
        print("   7) Dismiss alert")
        print("   8) Pupils at risk (severity ≥ High)")
        print("   9) Cohort summary")
        print("  10) Delete alert")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new, "2": _list, "3": _view,
            "4": _edit, "5": _set_status,
            "6": _resolve, "7": _dismiss,
            "8": _at_risk, "9": _summary, "10": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.Alert | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"]   = ask("Pupil ID",
                            existing.pupil_id if existing else None)
    f["alert_type"] = ask(f"Type ({'/'.join(ALERT_TYPES)})",
                            existing.alert_type if existing
                            else "Academic")
    f["severity"]   = ask(f"Severity ({'/'.join(SEVERITIES)})",
                            existing.severity if existing else "Medium")
    f["title"]      = ask("Title",
                            existing.title if existing else None)
    f["details"]    = ask("Details",
                            existing.details if existing else None)
    f["source"]     = ask(f"Source ({'/'.join(SOURCES)})",
                            existing.source if existing else "Teacher")
    f["raised_by"]  = ask("Raised by",
                            existing.raised_by if existing else None)
    f["raised_date"] = ask("Raised date (YYYY-MM-DD, blank = today)",
                             existing.raised_date if existing else None)
    f["status"]     = ask(f"Status ({'/'.join(ALERT_STATUSES)})",
                            existing.status if existing else "Open")
    f["assigned_to"] = ask("Assigned to",
                             existing.assigned_to if existing else None)
    f["resolution"]  = ask("Resolution (required if Resolved/Dismissed)",
                             existing.resolution if existing else None)
    f["resolved_date"] = ask("Resolved date (YYYY-MM-DD, blank ok)",
                               existing.resolved_date if existing
                               else None)
    f["notes"]      = ask("Notes",
                            existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── New Early-Warning Alert ──")
    fields = _collect()
    a = data.create(fields)
    print(f"  Raised alert #{a.alert_id}: {a.title} "
          f"({a.severity}, {a.status})")


@_safe
def _list() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    sev = _prompt(f"  Severity ({'/'.join(SEVERITIES)}, blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(ALERT_STATUSES)}, blank): ") or None
    atype = _prompt(
        f"  Type ({'/'.join(ALERT_TYPES)}, blank): ") or None
    pid = _prompt("  Pupil ID (blank): ") or None
    rows = data.list_alerts(year_group=yg, severity=sev, status=status,
                              alert_type=atype, pupil_id=pid)
    print(f"\n  {len(rows)} alert(s):")
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
    aid = _ask_id("Alert ID")
    if aid is None:
        return
    a = data.get(aid)
    if a is None:
        print("  No alert with that ID.")
        return
    print(f"\n  ── Alert #{a.alert_id} ──")
    print(f"  Pupil:        {a.pupil_id} ({a.pupil_name or '-'}, "
          f"Yr {a.pupil_year or '-'})")
    print(f"  Type:         {a.alert_type}    Severity: {a.severity}")
    print(f"  Title:        {a.title}")
    print(f"  Details:      {a.details or '-'}")
    print(f"  Source:       {a.source}    Raised by: "
          f"{a.raised_by or '-'}    on {a.raised_date}")
    print(f"  Status:       {a.status}    Assigned: "
          f"{a.assigned_to or '-'}")
    print(f"  Resolution:   {a.resolution or '-'}    Resolved: "
          f"{a.resolved_date or '-'}")
    print(f"  Notes:        {a.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    aid = _ask_id("Alert ID")
    if aid is None:
        return
    existing = data.get(aid)
    if existing is None:
        print("  No alert with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect(existing)
    a = data.update(aid, fields)
    print(f"  Updated alert #{a.alert_id} (status {a.status})")


@_safe
def _set_status() -> None:
    aid = _ask_id("Alert ID")
    if aid is None:
        return
    a = data.get(aid)
    if a is None:
        print("  No alert with that ID.")
        return
    print(f"  Current: {a.status}")
    print(f"  Allowed: {', '.join(ALERT_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    a = data.set_status(aid, new)
    print(f"  Status now: {a.status}")


@_safe
def _resolve() -> None:
    aid = _ask_id("Alert ID")
    if aid is None:
        return
    res = _prompt("  Resolution: ")
    if not res:
        print("  Resolution required.")
        return
    a = data.resolve(aid, resolution=res)
    print(f"  Resolved #{a.alert_id} on {a.resolved_date}.")


@_safe
def _dismiss() -> None:
    aid = _ask_id("Alert ID")
    if aid is None:
        return
    res = _prompt("  Reason for dismissal: ")
    if not res:
        print("  Resolution required.")
        return
    a = data.dismiss(aid, resolution=res)
    print(f"  Dismissed #{a.alert_id}.")


@_safe
def _at_risk() -> None:
    sev = _prompt(
        f"  Minimum severity ({'/'.join(SEVERITIES)}) [High]: ") or "High"
    pupils = data.pupils_at_risk(severity_min=sev)
    print(f"\n  {len(pupils)} pupil(s) with open alerts at ≥ {sev}:")
    for pid, alerts in pupils.items():
        print(f"\n  Pupil {pid} — {len(alerts)} alert(s):")
        for a in alerts:
            print(f"    #{a.alert_id:<5} {a.severity:<8} "
                  f"{a.alert_type[:18]:<18} {a.title[:40]}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    s = data.cohort_summary(year_group=yg)
    print(f"\n  Total: {s['total']}    Open: {s['open']}")
    print(f"  Open Critical: {s['open_critical']}    "
          f"Open High: {s['open_high']}")
    print("  By severity: "
          + "   ".join(f"{k}: {v}" for k, v in s["by_severity"].items()))
    print("  By status:   "
          + "   ".join(f"{k}: {v}" for k, v in s["by_status"].items()))
    print("  By type:")
    for k, v in sorted(s["by_type"].items(), key=lambda kv: -kv[1]):
        print(f"    {k:<20} {v}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    aid = _ask_id("Alert ID")
    if aid is None:
        return
    a = data.get(aid)
    if a is None:
        print("  No alert with that ID.")
        return
    confirm = _prompt(
        f"  Delete alert #{aid} ({a.title})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete(aid)
    print(f"  Deleted alert #{aid}.")


_DISPATCH = {"Early Warning": open_early_warning}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching early_warning CLI label: %s", label)
    handler()
    return True
