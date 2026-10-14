"""
Financial Forecasting & Analytics — interactive CLI (admin only).

Command-line twin of the Finance GUI Forecasting and Analytics tabs
(``layout/_forecasting.py`` and ``analytics.py``).  The GUI-embedded
arithmetic now lives in ``domain/reporting/forecast_projections`` so both
interfaces share it; the heavier analyses come straight from
``domain/reporting/revenue_analytics/forecasting`` and ``domain/core/analytics``
(imported lazily — they pull in numpy at import time).

Covers: forecast summary cards, average-based forecast narrative, a growth
forecast with period/growth parameters, revenue and expense projections,
scenario planning (comparison table, data-driven and narrative), enrolment
projections, cash-flow and risk analysis, predictive analytics, the
comprehensive forecast report, and the dashboard datasets rendered as text
tables (with optional PNG charts).
"""

from __future__ import annotations

from datetime import datetime
import logging

from education_system.systems.university.domains.finance.domain.reporting import (
    forecast_projections as fp,
)
from education_system.systems.university.domains.finance.interfaces.cli.support import (
    header,
    money,
    offer_chart,
    print_table,
    prompt_bool,
    prompt_float,
    prompt_int,
    require_finance_access,
    run_menu,
    text,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Forecasting tab
# --------------------------------------------------------------------------- #
def _summary() -> None:
    horizon = prompt_int(text("finance_cli.forecasting.horizon", "Horizon (months)"), 6, minimum=1)
    summary = fp.forecast_summary(horizon)
    header(text("finance_cli.forecasting.summary_title", "FORECAST SUMMARY"))
    print_table(
        ("Metric", "Amount"),
        [
            (text("finance_cli.forecasting.projected_revenue", "Projected revenue ({n} mo)", n=horizon),
             money(summary["projected_revenue"])),
            (text("finance_cli.forecasting.projected_expenses", "Projected expenses ({n} mo)", n=horizon),
             money(summary["projected_expenses"])),
            (text("finance_cli.forecasting.expected_collections", "Expected collections"),
             money(summary["expected_collections"])),
            (text("finance_cli.forecasting.net_projection", "Net projection"),
             money(summary["net_projection"])),
        ],
        align=("<", ">"),
    )
    print()
    print(fp.forecast_summary_text(summary))


def _generate_forecast() -> None:
    months = prompt_int(text("finance_cli.forecasting.period", "Forecast period (months)"), 6,
                        minimum=1)
    print()
    print(fp.generate_forecast_text(months))


def _growth_forecast() -> None:
    months = prompt_int(text("finance_cli.forecasting.period", "Forecast period (months)"), 12,
                        minimum=1)
    growth_pct = prompt_float(text("finance_cli.forecasting.growth", "Growth rate (% per month)"), 5.0)
    result = fp.simple_growth_forecast(months, growth_pct / 100.0)
    header(text("finance_cli.forecasting.growth_title", "REVENUE FORECAST"))
    print(text("finance_cli.forecasting.baseline", "Baseline monthly revenue: {amount}",
               amount=money(result["baseline"])))
    print(text("finance_cli.forecasting.growth_line", "Growth rate: {pct:.2f}% per month",
               pct=growth_pct))
    print()
    print_table(("Month", "Projected"), [(m, money(a)) for m, a in result["projections"]],
                align=("<", ">"))
    print()
    print(text("finance_cli.forecasting.projected_total", "Projected total: {total}",
               total=money(result["total"])))
    offer_chart(f"revenue_forecast_{datetime.now():%Y%m%d}.png", "line",
                [m for m, _ in result["projections"]], [a for _, a in result["projections"]],
                "Revenue Forecast", "Revenue (£)")


def _revenue_projection() -> None:
    print(fp.revenue_projection_report())
    series = fp.revenue_projection()["series"]
    offer_chart("revenue_projection.png", "bar", [m for m, _ in series], [v for _, v in series],
                "Historical Revenue (Last 12 Months)", "Revenue (£)")


def _expense_projection() -> None:
    print(fp.expense_projection_report())
    series = fp.expense_projection()["series"]
    offer_chart("expense_projection.png", "bar", [m for m, _ in series], [v for _, v in series],
                "Historical Expenses (Last 12 Months)", "Expenses (£)")


# --------------------------------------------------------------------------- #
# Analytics tab (domain report printers)
# --------------------------------------------------------------------------- #
def _core_analytics():
    from education_system.systems.university.domains.finance.domain.core import analytics

    return analytics


def _forecasting_module(auth):
    from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics import (
        forecasting,
    )

    # The domain printer gates on its own module-level ``auth``; hand it the
    # CLI session so the logged-in user is the one checked.
    forecasting.auth = auth
    return forecasting


def _scenario_planning() -> None:
    header(text("finance_cli.forecasting.scenarios_title", "SCENARIO COMPARISON"))
    print_table(("Scenario", "Students", "Revenue", "Expenses", "Net"),
                list(fp.SCENARIO_COMPARISON_ROWS), align=("<", ">", ">", ">", ">"))
    print()
    _core_analytics().generate_scenario_planning()
    if prompt_bool(text("finance_cli.forecasting.show_narrative",
                        "Show the full scenario planning narrative?")):
        print(fp.scenario_planning_text())


def _enrolment_projections() -> None:
    _core_analytics().generate_enrollment_projections()


def _cash_flow() -> None:
    _core_analytics().generate_cash_flow_analysis()


def _risk_analysis() -> None:
    _core_analytics().generate_risk_analysis()


def _section(title: str, headers: tuple, rows: list, align: tuple, empty: str) -> None:
    print("\n" + title)
    if rows:
        print_table(headers, rows, align=align)
    else:
        print(empty)


def _dashboard() -> None:
    year = prompt_int(text("finance_cli.forecasting.year", "Year"), datetime.now().year, minimum=2000)
    data = fp.dashboard_datasets(year)
    header(text("finance_cli.forecasting.dashboard_title", "FINANCIAL DASHBOARD {year}", year=year), 70)

    monthly = data["monthly_revenue"]
    methods = data["payment_methods"]
    outstanding = data["outstanding_by_course"]
    plans = data["payment_plan_status"]

    _section(text("finance_cli.forecasting.monthly_revenue", "Monthly revenue trend"),
             ("Month", "Revenue"), [(m, money(v)) for m, v in monthly], ("<", ">"),
             text("finance_cli.forecasting.no_revenue", "No revenue data."))
    _section(text("finance_cli.forecasting.payment_methods", "Payment methods"),
             ("Method", "Count", "Amount"), [(m, c, money(a)) for m, c, a in methods],
             ("<", ">", ">"), text("finance_cli.forecasting.no_payments", "No payment data."))
    _section(text("finance_cli.forecasting.outstanding", "Outstanding fees by course (top 10)"),
             ("Course", "Outstanding"), [(c, money(v)) for c, v in outstanding], ("<", ">"),
             text("finance_cli.forecasting.no_outstanding", "No outstanding fees."))
    _section(text("finance_cli.forecasting.plan_status", "Payment plan status"),
             ("Status", "Plans", "Total"), [(s, c, money(t)) for s, c, t in plans],
             ("<", ">", ">"), text("finance_cli.forecasting.no_plans", "No payment plans."))

    offer_chart(f"dashboard_revenue_{year}.png", "line", [f"Month {m}" for m, _ in monthly],
                [v for _, v in monthly], "Monthly Revenue Trend", "Revenue (£)")
    offer_chart(f"dashboard_methods_{year}.png", "pie", [m for m, _, _ in methods],
                [a for _, _, a in methods], "Payment Methods (by amount)")
    offer_chart(f"dashboard_outstanding_{year}.png", "bar", [c for c, _ in outstanding],
                [v for _, v in outstanding], "Outstanding Fees by Course", "Amount (£)")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_forecasting_menu(auth) -> None:
    """Run the Forecasting & Analytics CLI loop (admin only, like the GUI tabs)."""
    if not require_finance_access(auth, admin_only=True):
        return

    def _revenue_forecasting_system() -> None:
        _forecasting_module(auth).generate_revenue_forecast()

    def _predictive_analytics() -> None:
        _forecasting_module(auth).generate_predictive_analytics()

    def _comprehensive_report() -> None:
        _forecasting_module(auth).generate_comprehensive_forecast_report()

    run_menu(
        text("finance_cli.forecasting.title", "FINANCIAL FORECASTING & ANALYTICS"),
        (
            (text("finance_cli.forecasting.opt_summary", "Forecast summary"), _summary),
            (text("finance_cli.forecasting.opt_generate", "Generate forecast (historical average)"),
             _generate_forecast),
            (text("finance_cli.forecasting.opt_growth", "Revenue forecast (period + growth rate)"),
             _growth_forecast),
            (text("finance_cli.forecasting.opt_revenue_proj", "Revenue projection analysis"),
             _revenue_projection),
            (text("finance_cli.forecasting.opt_expense_proj", "Expense projection analysis"),
             _expense_projection),
            (text("finance_cli.forecasting.opt_seasonal", "Revenue forecasting system (seasonal model)"),
             _revenue_forecasting_system),
            (text("finance_cli.forecasting.opt_enrolment", "Enrolment projections"),
             _enrolment_projections),
            (text("finance_cli.forecasting.opt_cash_flow", "Cash flow analysis"), _cash_flow),
            (text("finance_cli.forecasting.opt_risk", "Risk analysis"), _risk_analysis),
            (text("finance_cli.forecasting.opt_scenarios", "Scenario planning & comparison"),
             _scenario_planning),
            (text("finance_cli.forecasting.opt_predictive", "Predictive analytics"),
             _predictive_analytics),
            (text("finance_cli.forecasting.opt_comprehensive", "Comprehensive forecast report"),
             _comprehensive_report),
            (text("finance_cli.forecasting.opt_dashboard", "Financial dashboard (tables / PNG)"),
             _dashboard),
        ),
    )


__all__ = ["run_forecasting_menu"]
