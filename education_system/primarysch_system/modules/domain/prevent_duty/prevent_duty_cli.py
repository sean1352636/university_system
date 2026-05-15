"""CLI handlers for Prevent-duty referrals."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.prevent_duty import (
    prevent_duty as data,
)
from education_system.primarysch_system.modules.domain.prevent_duty.prevent_duty import (
    CONCERN_TYPES, RISK_LEVELS, REFERRAL_PATHWAYS, STATUSES, OUTCOMES,
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


def _print_table(rows: list[data.Referral]) -> None:
    if not rows:
        print("  (no referrals)")
        return
    print(f"  {'ID':<5} {'Pupil':<10} {'Yr':<3} {'Raised':<11} "
          f"{'Concern':<22} {'Risk':<10} {'Pathway':<22} "
          f"{'Status':<22}")
    print(f"  {'-'*5} {'-'*10} {'-'*3} {'-'*11} {'-'*22} "
          f"{'-'*10} {'-'*22} {'-'*22}")
    for r in rows:
        print(f"  {r.referral_id:<5} {r.pupil_id:<10} "
              f"{(r.pupil_year or '-'):<3} {r.raised_date:<11} "
              f"{r.concern_type[:22]:<22} {r.risk_level:<10} "
              f"{r.referral_pathway[:22]:<22} "
              f"{r.status[:22]:<22}")


@_safe
def open_prevent_duty() -> None:
    logger.debug("CLI: open_prevent_duty")
    while True:
        print("\n  ── Prevent Duty ──")
        print("   1) New referral")
        print("   2) List referrals")
        print("   3) View referral")
        print("   4) Edit referral")
        print("   5) Set status")
        print("   6) Close referral")
        print("   7) Cohort summary")
        print("   8) Delete referral")
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


def _yn_default(label: str, current: bool | None) -> bool:
    sfx = f"[{'y' if current else 'n'}]"
    v = _prompt(f"  {label} {sfx} (y/n): ")
    if not v:
        return bool(current)
    return v.lower() == "y"


def _collect(existing: data.Referral | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"] = ask("Pupil ID",
                          existing.pupil_id if existing else None)
    f["concern_type"] = ask(
        f"Concern ({' | '.join(CONCERN_TYPES)})",
        existing.concern_type if existing
            else "Vulnerability to radicalisation")
    f["risk_level"]   = ask(
        f"Risk ({'/'.join(RISK_LEVELS)})",
        existing.risk_level if existing else "Low")
    f["raised_by"]    = ask("Raised by",
                              existing.raised_by if existing else None)
    f["raised_date"]  = ask(
        "Raised date (YYYY-MM-DD, blank = today)",
        existing.raised_date if existing else None)
    f["dsl_informed"] = _yn_default(
        "DSL informed?",
        existing.dsl_informed if existing else False)
    if f["dsl_informed"]:
        f["dsl_name"] = ask(
            "DSL name",
            existing.dsl_name if existing else None)
        f["dsl_informed_date"] = ask(
            "DSL informed date",
            existing.dsl_informed_date if existing else None)
    else:
        f["dsl_name"] = None
        f["dsl_informed_date"] = None
    f["description"] = ask("Description",
                              existing.description if existing else None)
    f["indicators"]  = ask("Indicators (concerning behaviours)",
                              existing.indicators if existing else None)
    f["online_activity"] = ask(
        "Online activity",
        existing.online_activity if existing else None)
    f["referral_pathway"] = ask(
        f"Pathway ({' | '.join(REFERRAL_PATHWAYS)})",
        existing.referral_pathway if existing
            else "Internal monitoring")
    f["referral_date"]    = ask(
        "Referral date",
        existing.referral_date if existing else None)
    f["referral_ref"]     = ask(
        "Referral ref / case #",
        existing.referral_ref if existing else None)
    f["agencies_involved"] = ask(
        "Agencies involved",
        existing.agencies_involved if existing else None)
    f["parents_informed"]  = _yn_default(
        "Parents informed?",
        existing.parents_informed if existing else False)
    if f["parents_informed"]:
        f["parents_informed_date"] = ask(
            "Parents informed date",
            existing.parents_informed_date if existing else None)
    else:
        f["parents_informed_date"] = None
    f["next_review_date"] = ask(
        "Next review date",
        existing.next_review_date if existing else None)
    f["status"]   = ask(
        f"Status ({' | '.join(STATUSES)})",
        existing.status if existing else "Open")
    f["outcome"]  = ask(
        f"Outcome ({' | '.join(OUTCOMES)})",
        existing.outcome if existing else "Pending")
    f["closed_date"]   = ask(
        "Closed date (only when status starts with Closed)",
        existing.closed_date if existing else None)
    f["closure_notes"] = ask(
        "Closure notes",
        existing.closure_notes if existing else None)
    f["notes"]    = ask("Notes",
                          existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── New Prevent Referral ──")
    fields = _collect()
    if not fields.get("pupil_id"):
        print("  Cancelled.")
        return
    r = data.create(fields)
    print(f"  Created referral #{r.referral_id}: {r.pupil_id} — "
          f"{r.concern_type} ({r.risk_level}, {r.status})")


@_safe
def _list() -> None:
    pid = _prompt("  Pupil ID (blank): ") or None
    status = _prompt(
        f"  Status ({' | '.join(STATUSES)}, blank): ") or None
    risk = _prompt(
        f"  Risk ({'/'.join(RISK_LEVELS)}, blank): ") or None
    open_only = _prompt("  Open only? (y/N): ").lower() == "y"
    rows = data.list_referrals(
        pupil_id=pid, status=status, risk_level=risk,
        open_only=open_only)
    print(f"\n  {len(rows)} referral(s):")
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
    rid = _ask_id("Referral ID")
    if rid is None:
        return
    r = data.get(rid)
    if r is None:
        print("  No referral with that ID.")
        return
    print(f"\n  ── Referral #{r.referral_id} ──")
    print(f"  Pupil:        {r.pupil_id} ({r.pupil_name or '-'}, "
          f"Yr {r.pupil_year or '-'})")
    print(f"  Concern:      {r.concern_type}")
    print(f"  Risk:         {r.risk_level}")
    print(f"  Raised by:    {r.raised_by} on {r.raised_date}")
    print(f"  DSL:          "
          f"{'Yes' if r.dsl_informed else 'No'}    "
          f"{r.dsl_name or '-'} on {r.dsl_informed_date or '-'}")
    print(f"  Description:  {r.description}")
    print(f"  Indicators:   {r.indicators or '-'}")
    print(f"  Online:       {r.online_activity or '-'}")
    print(f"  Pathway:      {r.referral_pathway}    "
          f"on {r.referral_date or '-'}    "
          f"ref: {r.referral_ref or '-'}")
    print(f"  Agencies:     {r.agencies_involved or '-'}")
    print(f"  Parents:      "
          f"{'Yes' if r.parents_informed else 'No'} on "
          f"{r.parents_informed_date or '-'}")
    print(f"  Next review:  {r.next_review_date or '-'}")
    print(f"  Status:       {r.status}    Outcome: {r.outcome}")
    print(f"  Closed:       {r.closed_date or '-'}")
    print(f"  Closure note: {r.closure_notes or '-'}")
    print(f"  Notes:        {r.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    rid = _ask_id("Referral ID")
    if rid is None:
        return
    existing = data.get(rid)
    if existing is None:
        print("  No referral with that ID.")
        return
    fields = _collect(existing)
    data.update(rid, fields)
    print(f"  Updated referral #{rid}.")


@_safe
def _set_status() -> None:
    rid = _ask_id("Referral ID")
    if rid is None:
        return
    r = data.get(rid)
    if r is None:
        print("  No referral with that ID.")
        return
    print(f"  Current: {r.status}    Outcome: {r.outcome}")
    print(f"  Allowed: {', '.join(STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    outcome = _prompt(
        f"  Outcome (blank to keep '{r.outcome}'): ") or None
    r = data.set_status(rid, new, outcome=outcome)
    print(f"  Status now: {r.status}    Outcome: {r.outcome}")


@_safe
def _close() -> None:
    rid = _ask_id("Referral ID")
    if rid is None:
        return
    print(f"  Closed statuses: "
          + ", ".join(s for s in STATUSES if s.startswith("Closed")))
    status = _prompt("  Closed status: ").strip()
    if not status:
        return
    outcome = _prompt(
        f"  Outcome ({' | '.join(OUTCOMES)}): ").strip()
    if not outcome:
        print("  Cancelled (outcome required).")
        return
    notes = _prompt("  Closure notes (blank): ") or None
    r = data.close_referral(
        rid, outcome=outcome, status=status,
        closure_notes=notes)
    print(f"  Closed referral #{r.referral_id} on {r.closed_date} "
          f"(outcome: {r.outcome}).")


@_safe
def _summary() -> None:
    frm = _prompt("  From date (blank): ") or None
    to  = _prompt("  To date (blank): ") or None
    s = data.cohort_summary(from_date=frm, to_date=to)
    print(f"\n  Total: {s['total']}   Open: {s['open']}   "
          f"High-risk: {s['high_risk']}")
    print(f"  Channel: {s['channel']}   Police: {s['police']}   "
          f"Pupils: {s['pupils']}")
    print(f"  DSL informed: {s['dsl_informed']}   "
          f"Parents informed: {s['parents_informed']}")
    print(f"  By status:  "
          + "   ".join(f"{k}: {v}" for k, v in s["by_status"].items()))
    print(f"  By risk:    "
          + "   ".join(f"{k}: {v}" for k, v in s["by_risk"].items()))
    print(f"  By concern: "
          + "   ".join(f"{k}: {v}" for k, v in s["by_concern"].items()))
    print(f"  By pathway: "
          + "   ".join(f"{k}: {v}" for k, v in s["by_pathway"].items()))
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    rid = _ask_id("Referral ID")
    if rid is None:
        return
    r = data.get(rid)
    if r is None:
        print("  No referral with that ID.")
        return
    confirm = _prompt(
        f"  Delete referral #{rid} ({r.pupil_id}, "
        f"{r.concern_type})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete(rid):
        print(f"  Deleted referral #{rid}.")


_DISPATCH = {"Prevent Duty": open_prevent_duty}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching prevent_duty CLI label: %s", label)
    handler()
    return True
