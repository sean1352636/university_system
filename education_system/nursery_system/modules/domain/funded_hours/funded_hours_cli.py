"""CLI flow for Funded Hours (15/30 & 2-Year-Old) (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.funded_hours import (
    funded_hours as data,
)
from education_system.nursery_system.modules.domain.funded_hours.funded_hours import (
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


def _print_table(rows: list[data.FundedHoursRecord]) -> None:
    if not rows:
        print("  (no funded-hours records)")
        return
    print(f"  {'ID':<8} {'Child':<22} {'Entitlement':<20} {'Funded':<8} "
          f"{'Code':<13} {'Status'}")
    print(f"  {'-'*8} {'-'*22} {'-'*20} {'-'*8} {'-'*13} {'-'*8}")
    for r in rows:
        funded = f"{r.funded_hours_pw:g}h" if r.funded_hours_pw is not None else "-"
        print(f"  {r.record_id:<8} {(r.child_name or '-')[:22]:<22} "
              f"{r.entitlement[:20]:<20} {funded:<8} "
              f"{(r.eligibility_code or '-'):<13} {r.status}")


def _print_detail(r: data.FundedHoursRecord) -> None:
    print(f"\n  ── Funded hours {r.record_id} ──")
    print(f"  Child:             {r.child_name or '-'} ({r.pupil_id})")
    print(f"  Room:              {r.room or '-'}")
    print(f"  Entitlement:       {r.entitlement}")
    print(f"  Funded hours/week: {r.funded_hours_pw:g}" if r.funded_hours_pw
          is not None else "  Funded hours/week: -")
    print(f"  Additional hours:  {r.additional_hours:g}" if r.additional_hours
          else "  Additional hours:  0")
    print(f"  Total hours:       {r.total_hours:g}")
    print(f"  Eligibility code:  {r.eligibility_code or '-'}")
    print(f"  Eligible:          {r.eligibility_start or '-'} → {r.eligibility_end or '-'}")
    print(f"  Funding period:    {r.funding_period or '-'}")
    print(f"  Stretched offer:   {'Yes' if r.stretched else 'No'}")
    print(f"  Status:            {r.status}")
    print(f"  Notes:             {r.notes or '-'}")


def _show_children() -> None:
    try:
        choices = data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return
    if choices:
        print("  Children:")
        for _id, label in choices:
            print(f"    {label}")


def _collect_fields(existing: data.FundedHoursRecord | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["entitlement"]      = ask(f"Entitlement ({'/'.join(ENTITLEMENTS)})",
                                     existing.entitlement if existing else None)
    fields["funded_hours_pw"]  = ask("Funded hours/week",
                                     existing.funded_hours_pw if existing else None)
    fields["additional_hours"] = ask("Additional paid hours/week",
                                     existing.additional_hours if existing else None)
    fields["eligibility_code"] = ask("Eligibility code (30h = 11 digits)",
                                     existing.eligibility_code if existing else None)
    fields["eligibility_start"] = ask("Eligible from (YYYY-MM-DD)",
                                      existing.eligibility_start if existing else None)
    fields["eligibility_end"]  = ask("Eligible until (YYYY-MM-DD)",
                                     existing.eligibility_end if existing else None)
    fields["funding_period"]   = ask("Funding period (e.g. 2024/25)",
                                     existing.funding_period if existing else None)
    stretched_cur = ("y" if existing.stretched else "n") if existing else None
    fields["stretched"]        = ask("Stretched offer? (y/n)", stretched_cur)
    fields["notes"]            = ask("Notes", existing.notes if existing else None)
    if existing is not None:
        fields["status"] = ask(f"Status ({'/'.join(STATUSES)})", existing.status)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: funded_hours open_manager")
    show_ended = True
    while True:
        s = data.summary()
        scope = "all" if show_ended else "active only"
        print(f"\n  ── Funded Hours (15/30 & 2-Year-Old) ({scope}) ──")
        print(f"  Active records: {s['records']}   "
              f"Total funded hrs/wk: {s['funded_hours_total']:g}")
        if s["by_entitlement"]:
            print("  By entitlement: " + "  ".join(
                f"{k}={v}" for k, v in sorted(s["by_entitlement"].items())))
        _print_table(data.list_records(include_ended=show_ended))
        print("\n   A) Add    V) View    E) Edit    D) Delete")
        print("   X) End / reactivate    T) Toggle ended    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            rid = _prompt("  Record ID: ")
            r = data.get_record(rid)
            if r is None:
                print("  No record with that ID.")
            else:
                _print_detail(r)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "x":
            open_toggle_status()
        elif choice == "t":
            show_ended = not show_ended
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    logger.debug("CLI: funded_hours open_add")
    print("\n  ── Add Funded-Hours Record ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    r = data.create_record(fields)
    print(f"\n  Created funded-hours record {r.record_id} for {r.child_name} "
          f"({r.entitlement}).")


@_safe
def open_edit() -> None:
    logger.debug("CLI: funded_hours open_edit")
    rid = _prompt("  Record ID: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    r = data.update_record(rid, fields)
    print(f"\n  Updated funded-hours record {r.record_id}.")


@_safe
def open_delete() -> None:
    logger.debug("CLI: funded_hours open_delete")
    rid = _prompt("  Record ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    confirm = _prompt(
        f"  Delete funded-hours record {rid} for {existing.child_name}? (y/N): "
    ).lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_record(rid):
        print(f"  Deleted record {rid}.")
    else:
        print("  Could not delete (already removed?).")


@_safe
def open_toggle_status() -> None:
    rid = _prompt("  Record ID to end/reactivate: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    new_status = "ended" if existing.status == "active" else "active"
    r = data.set_status(rid, new_status)
    print(f"  Record {r.record_id} is now {r.status}.")


_DISPATCH = {"Funded Hours (15/30 & 2-Year-Old)": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching funded_hours CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
