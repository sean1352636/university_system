"""CLI flow for Payroll & Staffing Costs (Nursery System)."""

from __future__ import annotations

import datetime as _dt
import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.payroll import (
    payroll as data,
)
from education_system.nursery_system.modules.domain.payroll.payroll import (
    PAY_STATUSES,
    PAY_TYPES,
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


def _ask(label: str, current=None) -> str:
    cur = "" if current is None else str(current)
    suffix = f" [{cur}]" if cur else ""
    v = _prompt(f"  {label}{suffix}: ")
    return v if v else cur


def _ask_bool(label: str, current: bool | None) -> str:
    cur = "" if current is None else ("y" if current else "n")
    suffix = f" [{cur}]" if cur else ""
    v = _prompt(f"  {label} (y/n){suffix}: ").lower()
    return v if v else cur


def _this_monday() -> str:
    today = _dt.date.today()
    return (today - _dt.timedelta(days=today.weekday())).isoformat()


@_safe
def open_manager() -> None:
    logger.debug("CLI: payroll open_manager")
    while True:
        s = data.summary()
        print("\n  ── Payroll & Staffing Costs ──")
        print(f"  On payroll: {s['staff_on_payroll']}   "
              f"Agency: {s['agency_staff']}")
        print(f"  Week of {s['week_start']}: {s['week_hours']}h worked "
              f"({s['week_overtime_hours']}h overtime, "
              f"{s['week_absent_hours']}h lost to absence)")
        print(f"  Gross £{s['week_gross']:.2f} + on-costs "
              f"£{s['week_on_costs']:.2f} = £{s['week_total']:.2f}"
              + (f"   (agency £{s['week_agency_cost']:.2f})"
                 if s["week_agency_cost"] else ""))
        print(f"  Next 4 weeks: £{s['forecast_4_weeks']:.2f} "
              f"(avg £{s['forecast_weekly_average']:.2f}/week)")
        if s["missing_pay_records"]:
            print(f"  ⚠ {s['missing_pay_records']} employed staff have no pay "
                  "record — costs below understate the real bill.")
        print("\n   R) Pay rates    W) This week    P) A period    M) A month")
        print("   F) Forecast    G) Staff with no pay record    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "r":
            open_rates()
        elif choice == "w":
            _print_period(data.week_cost(_this_monday()))
            _prompt("  Press Enter to continue...")
        elif choice == "p":
            open_period()
        elif choice == "m":
            open_month()
        elif choice == "f":
            open_forecast()
        elif choice == "g":
            open_gaps()
        else:
            print("  Invalid selection.")


# ── Pay rates ────────────────────────────────────────────────────────────────

def _print_rates(rows: list[data.PayRecord]) -> None:
    if not rows:
        print("  (no pay records)")
        return
    print(f"  {'Staff':<24} {'Role':<22} {'Type':<10} {'Rate':>9} "
          f"{'Hours':>7} {'OT':>5} {'NI%':>6} {'Pen%':>6} {'Agency'}")
    print(f"  {'-'*24} {'-'*22} {'-'*10} {'-'*9} {'-'*7} {'-'*5} {'-'*6} "
          f"{'-'*6} {'-'*14}")
    for p in rows:
        print(f"  {(p.staff_name or p.staff_id)[:24]:<24} "
              f"{(p.role or '-')[:22]:<22} {p.pay_type:<10} "
              f"£{p.effective_hourly_rate:>8.2f} {p.contracted_hours:>7g} "
              f"{p.overtime_multiplier:>5g} {p.ni_percent:>6g} "
              f"{p.pension_percent:>6g} {p.agency_name or ''}")


@_safe
def open_rates() -> None:
    while True:
        print("\n  ── Pay Rates ──")
        _print_rates(data.list_pay_records())
        print("\n   S) Set a rate    D) Delete a record    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "s":
            open_set_rate()
        elif choice == "d":
            sid = _prompt("  Staff ID: ")
            if sid and _prompt(f"  Delete the pay record for {sid}? (y/N): "
                               ).lower() == "y":
                print(f"  Deleted." if data.delete_pay_record(sid)
                      else "  No pay record for that staff member.")
        else:
            print("  Invalid selection.")


@_safe
def open_set_rate() -> None:
    print("\n  ── Set a Pay Rate ──")
    for sid, label in data.list_staff_choices():
        print(f"    {sid}  {label}")
    staff_id = _prompt("  Staff ID: ")
    if not staff_id:
        print("  Cancelled.")
        return
    existing = data.get_pay_record(staff_id)
    if existing:
        print("  Press Enter to keep the existing value.")
    fields = {
        "pay_type": _ask(f"Pay type ({'/'.join(PAY_TYPES)})",
                         existing.pay_type if existing else "hourly"),
        "hourly_rate": _ask("Hourly rate (£)",
                            existing.hourly_rate if existing else None),
        "annual_salary": _ask("Annual salary (£, salaried only)",
                              existing.annual_salary if existing else None),
        "contracted_hours": _ask("Contracted hours per week",
                                 existing.contracted_hours if existing else None),
        "overtime_multiplier": _ask(
            "Overtime multiplier",
            existing.overtime_multiplier if existing else 1.5),
        "is_agency": _ask_bool("Agency staff?",
                               existing.is_agency if existing else None),
        "agency_name": _ask("Agency name",
                            existing.agency_name if existing else None),
        "ni_percent": _ask("Employer NI %",
                           existing.ni_percent if existing else 13.8),
        "pension_percent": _ask("Employer pension %",
                                existing.pension_percent if existing else 3.0),
        "effective_from": _ask("Effective from",
                               existing.effective_from if existing else None),
        "status": _ask(f"Status ({'/'.join(PAY_STATUSES)})",
                       existing.status if existing else "active"),
        "notes": _ask("Notes", existing.notes if existing else None),
    }
    p = data.set_pay(staff_id, fields)
    print(f"\n  Saved. {p.staff_name or staff_id}: "
          f"£{p.effective_hourly_rate:.2f}/hour basic, "
          f"£{p.overtime_rate:.2f}/hour overtime, "
          f"{p.on_cost_percent:g}% employer on-costs.")


# ── Costed periods ───────────────────────────────────────────────────────────

def _print_period(period: data.PeriodCost) -> None:
    print(f"\n  ── Staffing cost {period.date_from} to {period.date_to} ──")
    rows = [s for s in period.staff if s.worked_hours or s.absent_hours]
    if not rows:
        print("  (no rota hours in this period)")
    else:
        print(f"  {'Staff':<24} {'Shifts':>7} {'Hours':>7} {'OT':>6} "
              f"{'Absent':>7} {'Gross':>10} {'On-costs':>10} {'Total':>10}")
        print(f"  {'-'*24} {'-'*7} {'-'*7} {'-'*6} {'-'*7} {'-'*10} {'-'*10} "
              f"{'-'*10}")
        for s in rows:
            flag = "" if s.has_pay_record else "  (no pay record)"
            print(f"  {(s.staff_name or s.staff_id)[:24]:<24} {s.shifts:>7} "
                  f"{s.worked_hours:>7g} {s.overtime_hours:>6g} "
                  f"{s.absent_hours:>7g} £{s.gross_pay:>9.2f} "
                  f"£{s.ni_cost + s.pension_cost:>9.2f} "
                  f"£{s.total_cost:>9.2f}{flag}")
    print(f"\n  Hours: {period.worked_hours}   Overtime: "
          f"{period.overtime_hours}   Lost to absence: {period.absent_hours}")
    print(f"  Gross £{period.gross_pay:.2f} + on-costs £{period.on_costs:.2f} "
          f"= £{period.total_cost:.2f}")
    if period.agency_cost:
        print(f"  Of which agency: £{period.agency_cost:.2f}")
    if period.overtime_cost:
        print(f"  Of which overtime: £{period.overtime_cost:.2f}")
    missing = period.missing_pay_records
    if missing:
        print(f"  ⚠ No pay record for: {', '.join(missing[:8])}"
              + (" …" if len(missing) > 8 else ""))


@_safe
def open_period() -> None:
    date_from = _prompt("  From (YYYY-MM-DD): ")
    date_to = _prompt("  To (YYYY-MM-DD): ")
    _print_period(data.period_cost(date_from, date_to))
    _prompt("  Press Enter to continue...")


@_safe
def open_month() -> None:
    today = _dt.date.today()
    year = _prompt(f"  Year [{today.year}]: ") or str(today.year)
    month = _prompt(f"  Month [{today.month}]: ") or str(today.month)
    try:
        _print_period(data.month_cost(int(year), int(month)))
    except ValueError:
        print("  Year and month must be numbers.")
        return
    _prompt("  Press Enter to continue...")


@_safe
def open_forecast() -> None:
    weeks = _prompt("  Weeks ahead [4]: ") or "4"
    try:
        result = data.forecast_total(int(weeks))
    except ValueError:
        print("  Weeks must be a number.")
        return
    print(f"\n  ── Staffing forecast, {result['from']} to {result['to']} ──")
    print(f"  {'Week':<26} {'Hours':>9} {'Cost':>12}")
    print(f"  {'-'*26} {'-'*9} {'-'*12}")
    for w in result["weekly"]:
        print(f"  {w['from']} to {w['to']:<10} {w['hours']:>9g} "
              f"£{w['cost']:>11.2f}")
    print(f"\n  Total: £{result['total_cost']:.2f} over {result['weeks']} "
          f"week(s), averaging £{result['average_weekly_cost']:.2f}/week")
    print(f"  Gross £{result['gross_pay']:.2f} + on-costs "
          f"£{result['on_costs']:.2f}   Overtime £{result['overtime_cost']:.2f}"
          f"   Agency £{result['agency_cost']:.2f}")
    print("  Weeks the rota doesn't reach are priced at contracted hours.")
    _prompt("  Press Enter to continue...")


@_safe
def open_gaps() -> None:
    rows = data.staff_without_pay()
    print("\n  ── Staff With No Pay Record ──")
    if not rows:
        print("  Every employed staff member has a pay arrangement.")
    else:
        for sid, name in rows:
            print(f"    {name} ({sid})")
        print("\n  Their hours are counted but cost nothing until a rate is set.")
    _prompt("  Press Enter to continue...")


_DISPATCH = {"Payroll & Staffing Costs": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching payroll CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
