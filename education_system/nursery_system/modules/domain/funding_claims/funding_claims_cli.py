"""CLI flow for Funded Hours Claims (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.funding_claims import (
    funding_claims as data,
)
from education_system.nursery_system.modules.domain.funding_claims.funding_claims import (
    ENTITLEMENTS,
    STATUSES,
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
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_table(rows: list[data.FundingClaim]) -> None:
    if not rows:
        print("  (no funding claims)")
        return
    print(f"  {'ID':<8} {'Period':<14} {'Child':<18} {'Entitlement':<18} "
          f"{'Amount':>10}  {'Status'}")
    print(f"  {'-'*8} {'-'*14} {'-'*18} {'-'*18} {'-'*10}  {'-'*9}")
    for c in rows:
        print(f"  {c.claim_id:<8} {(c.funding_period or '-')[:14]:<14} "
              f"{(c.child_name or 'whole setting')[:18]:<18} "
              f"{(c.entitlement or '-')[:18]:<18} {c.claim_amount:>10.2f}  "
              f"{c.status}")


def _print_detail(c: data.FundingClaim) -> None:
    print(f"\n  ── Funding claim {c.claim_id} ──")
    print(f"  Child:          {c.child_name or '(whole setting)'} "
          f"({c.pupil_id or '-'})")
    print(f"  Period:         {c.funding_period or '-'}")
    print(f"  Entitlement:    {c.entitlement or '-'}")
    print(f"  Funded hours:   {c.funded_hours or '-'} /week")
    print(f"  Weeks:          {c.weeks or '-'}")
    print(f"  Hourly rate:    £{c.hourly_rate or 0:.2f}")
    print(f"  Claim amount:   £{c.claim_amount:.2f}")
    print(f"  Headcount date: {c.headcount_date or '-'}")
    print(f"  Status:         {c.status}")
    print(f"  Submitted:      {c.submitted_date or '-'}")
    print(f"  Notes:          {c.notes or '-'}")


def _show_children() -> None:
    try:
        choices = data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return
    if choices:
        print("  Children (leave blank for a whole-setting claim):")
        for _id, label in choices:
            print(f"    {label}")


def _collect_fields(existing: data.FundingClaim | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if existing is None:
        _show_children()
    fields["pupil_id"]       = ask("Child ID (blank = whole setting)",
                                   existing.pupil_id if existing else None)
    fields["funding_period"] = ask("Funding period (e.g. Summer 2025)",
                                   existing.funding_period if existing else None)
    fields["entitlement"]    = ask(f"Entitlement ({'/'.join(ENTITLEMENTS)})",
                                   existing.entitlement if existing else None)
    fields["funded_hours"]   = ask("Funded hours/week",
                                   existing.funded_hours if existing else None)
    fields["weeks"]          = ask("Weeks in period",
                                   existing.weeks if existing else None)
    fields["hourly_rate"]    = ask("LA hourly rate (£)",
                                   existing.hourly_rate if existing else None)
    fields["headcount_date"] = ask("Headcount date (YYYY-MM-DD)",
                                   existing.headcount_date if existing else None)
    fields["status"]         = ask(f"Status ({'/'.join(STATUSES)})",
                                   existing.status if existing else "draft")
    fields["submitted_date"] = ask("Submitted date (YYYY-MM-DD)",
                                   existing.submitted_date if existing else None)
    fields["notes"]          = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: funding_claims open_manager")
    while True:
        s = data.summary()
        print("\n  ── Funded Hours Claims ──")
        print(f"  Claims: {int(s['count'])}   Total: £{s['total']:.2f}   "
              f"Submitted: £{s['submitted']:.2f}   Paid: £{s['paid']:.2f}")
        _print_table(data.list_claims())
        print("\n   A) Add    V) View    E) Edit    D) Delete")
        print("   S) Set status    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            cid = _prompt("  Claim ID: ")
            c = data.get_claim(cid)
            if c is None:
                print("  No claim with that ID.")
            else:
                _print_detail(c)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "s":
            open_set_status()
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Funding Claim ──")
    fields = _collect_fields()
    c = data.create_claim(fields)
    print(f"\n  Created claim {c.claim_id} for {c.funding_period or '-'} "
          f"(£{c.claim_amount:.2f}).")


@_safe
def open_edit() -> None:
    cid = _prompt("  Claim ID: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_claim(cid)
    if existing is None:
        print("  No claim with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    c = data.update_claim(cid, fields)
    print(f"\n  Updated claim {c.claim_id} (£{c.claim_amount:.2f}).")


@_safe
def open_delete() -> None:
    cid = _prompt("  Claim ID to delete: ")
    if not cid:
        print("  Cancelled.")
        return
    if data.get_claim(cid) is None:
        print("  No claim with that ID.")
        return
    if _prompt(f"  Delete claim {cid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_claim(cid):
        print(f"  Deleted claim {cid}.")
    else:
        print("  Could not delete (already removed?).")


@_safe
def open_set_status() -> None:
    cid = _prompt("  Claim ID: ")
    if not cid:
        print("  Cancelled.")
        return
    if data.get_claim(cid) is None:
        print("  No claim with that ID.")
        return
    status = _prompt(f"  New status ({'/'.join(STATUSES)}): ").lower()
    c = data.set_status(cid, status)
    print(f"  Claim {c.claim_id} is now {c.status}.")


_DISPATCH = {"Funded Hours Claims": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching funding_claims CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
