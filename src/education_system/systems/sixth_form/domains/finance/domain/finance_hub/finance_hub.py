"""Headline finance figures for the Sixth Form finance dashboard.

One read-only roll-up over every finance area — bursary payments and
holds, the 16-19 vulnerable bursary, free meals, trip refunds and
bursary-funded places, tuition invoices, fees, receipts, expense claims
and department budgets — used by the Finance hub's dashboard (GUI) and
the finance dashboard CLI. Each area is computed independently: one
failing area is reported as unavailable and never blanks the rest.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

CURRENCY_SYMBOL: str = "£"


def money(v: Any) -> str:
    try:
        x = float(v or 0)
    except (TypeError, ValueError):
        return "—"
    return f"{'-' if x < 0 else ''}{CURRENCY_SYMBOL}{abs(x):,.2f}"


@dataclass
class Figure:
    label: str
    value: str
    alert: bool = False         # needs attention (overdue, overspent, held)


@dataclass
class Area:
    key: str                    # matches a Finance hub section id
    title: str
    figures: list[Figure] = field(default_factory=list)
    error: str | None = None


@dataclass
class Dashboard:
    generated_at: str
    academic_year: str
    areas: list[Area] = field(default_factory=list)

    @property
    def alerts(self) -> list[str]:
        return [f"{a.title}: {f.label} {f.value}"
                for a in self.areas for f in a.figures if f.alert]

    def as_text(self) -> str:
        out = [f"Finance dashboard — {self.academic_year} "
               f"(as of {self.generated_at})", ""]
        for a in self.areas:
            out.append(a.title)
            out.append("-" * len(a.title))
            if a.error:
                out.append(f"  unavailable: {a.error}")
            for f in a.figures:
                out.append(f"  {'! ' if f.alert else '  '}{f.label:<34} "
                           f"{f.value}")
            out.append("")
        if self.alerts:
            out.append("Needs attention")
            out.append("---------------")
            out.extend(f"  ! {a}" for a in self.alerts)
        return "\n".join(out)


def _bursaries() -> list[Figure]:
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries as b,
    )
    s = b.summary()
    sch = b.schedule_summary()
    vulnerable = b.list_applications(bursary_type=b.VULNERABLE_TYPE,
                                     approved_only=True)
    awaiting = [a for a in b.list_applications(active_only=True)
                if not a.is_approved and not a.evidence_verified]
    return [
        Figure("Awarded / paid", f"{money(s.total_awarded)} / "
                                 f"{money(s.total_paid)}"),
        Figure("Still to pay on awards", money(s.total_remaining)),
        Figure("Instalments due now", f"{sch.due_now} "
               f"({money(sch.due_now_value)})", alert=sch.due_now > 0),
        Figure("Held on attendance", f"{sch.held} ({money(sch.held_value)})",
               alert=sch.held > 0),
        Figure("Forfeited", money(sch.forfeited_value)),
        Figure("Vulnerable bursaries awarded",
               f"{len(vulnerable)} "
               f"({money(sum(a.amount_awarded or 0 for a in vulnerable))})"),
        Figure("Applications awaiting evidence check", str(len(awaiting)),
               alert=bool(awaiting)),
    ]


def _free_meals() -> list[Figure]:
    from education_system.systems.sixth_form.domains.finance.domain.free_meals import (
        free_meals as fm,
    )
    s = fm.summary()
    allowance = fm.get_default_allowance()
    return [
        Figure("Active entitlements", str(s.active_entitlements)),
        Figure("Evidence not yet verified", str(s.unverified_evidence),
               alert=s.unverified_evidence > 0),
        Figure(f"Meals taken in {s.month}", str(s.meals_this_month)),
        Figure(f"Claim value {s.month}", money(s.claimed_this_month)),
        Figure("College days not recorded", str(s.unrecorded_this_month),
               alert=s.unrecorded_this_month > 0),
        Figure("Daily allowance", money(allowance) if allowance
               else "not set", alert=allowance is None
               and s.active_entitlements > 0),
    ]


def _trips() -> list[Figure]:
    from education_system.systems.sixth_form.domains.finance.domain.trips import (
        trips as t,
    )
    s = t.summary()
    return [
        Figure("Outstanding from learners", money(s.total_outstanding)),
        Figure("Overdue balances", money(s.overdue_balance),
               alert=s.overdue_balance > 0),
        Figure("Refunds due", f"{s.refunds_due_count} "
               f"({money(s.refunds_due_value)})",
               alert=s.refunds_due_count > 0),
        Figure("Refunded to date", money(s.total_refunded)),
        Figure("Places paid from bursaries", money(s.bursary_funded)),
    ]


def _fees(year: str) -> list[Figure]:
    from education_system.systems.sixth_form.domains.finance.domain.fees import (
        fee_rules as fr,
        fees as f,
    )
    s = f.summary()
    inv = fr.summary(year)
    return [
        Figure("Fees outstanding", money(s.total_outstanding)),
        Figure("Overdue", f"{s.overdue_count} ({money(s.overdue_total)})",
               alert=s.overdue_count > 0),
        Figure(f"Tuition invoices {year}", f"{inv.invoices_issued} "
               f"({money(inv.invoiced_total)})"),
        Figure("Tuition outstanding", money(inv.outstanding_total)),
        Figure("Remitted / waived", money(inv.remitted_total)),
        Figure("Learners with fee profiles", str(inv.profiles)),
    ]


def _receipts_expenses() -> list[Figure]:
    from education_system.systems.sixth_form.domains.finance.domain.expense_claims import (
        expense_claims as e,
    )
    from education_system.systems.sixth_form.domains.finance.domain.receipts import (
        receipts as r,
    )
    rs = r.summary()
    es = e.summary()
    return [
        Figure("Receipts issued (total)", money(rs.total_issued_amount)),
        Figure("Receipted this month", money(rs.daily_this_month)),
        Figure("Expense claims awaiting payment",
               money(es.awaiting_payment_value)),
        Figure("Open expense claims",
               str(es.submitted + es.under_review + es.approved)),
    ]


def _budgets(year: str) -> list[Figure]:
    from education_system.systems.sixth_form.domain.staff.departments import (
        department_budgets as db,
    )
    rows = db.all_departments(year)
    over = [r for r in rows if r.overspent]
    near = [r for r in rows if not r.overspent
            and (r.utilisation_pct or 0) >= db.WARN_AT_PCT]
    figs = [
        Figure("Departments budgeted", str(len(rows))),
        Figure("Total budget / net spend",
               f"{money(sum(r.budget for r in rows))} / "
               f"{money(sum(r.net_spend for r in rows))}"),
        Figure("Overspent departments", str(len(over)), alert=bool(over)),
        Figure(f"At {db.WARN_AT_PCT:.0f}%+ of budget", str(len(near)),
               alert=bool(near)),
    ]
    figs += [Figure(f"  {r.name}", f"{money(r.net_spend)} of "
                    f"{money(r.budget)}", alert=True) for r in over[:5]]
    return figs


def dashboard(academic_year: str | None = None) -> Dashboard:
    from education_system.systems.sixth_form.domains.finance.domain import (
        finance_calendar as fc,
    )
    year = fc.normalise_year(academic_year)
    dash = Dashboard(
        generated_at=_dt.datetime.now().isoformat(timespec="minutes"),
        academic_year=year)
    parts: list[tuple[str, str, Callable[[], list[Figure]]]] = [
        ("bursaries", "Bursaries (16-19 Bursary Fund)", _bursaries),
        ("bursaries", "Free meals", _free_meals),
        ("trips", "Trips", _trips),
        ("fees", "Fees and tuition", lambda: _fees(year)),
        ("receipts", "Receipts and expenses", _receipts_expenses),
        ("budgets", "Department budgets", lambda: _budgets(year)),
    ]
    for key, title, fn in parts:
        area = Area(key=key, title=title)
        try:
            area.figures = fn()
        except Exception as exc:  # noqa: BLE001 - one area never blanks the rest
            logger.exception("Finance dashboard: %s failed", title)
            area.error = str(exc) or type(exc).__name__
        dash.areas.append(area)
    return dash
