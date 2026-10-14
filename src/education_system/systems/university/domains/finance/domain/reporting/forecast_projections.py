"""Forecasting projections shared by the Finance GUI and CLI.

These functions were lifted out of the Finance GUI's Forecasting tab
(``interfaces/gui/finance/layout/_forecasting.py``) and Analytics manager
(``interfaces/gui/finance/analytics.py``) so both interfaces run the same
arithmetic against the same ``student_records.db`` tables.

Every function is pure data in / data out (dicts, lists, strings).  Nothing
here prints or touches a widget, and nothing is imported at module level
beyond the shared connection factory.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from education_system.systems.university.infrastructure.database.db import get_connection

#: Scenario comparison rows shown in the GUI "Scenarios" table.  Static
#: planning assumptions, kept in one place so the CLI table matches.
SCENARIO_COMPARISON_ROWS: tuple[tuple[str, str, str, str, str], ...] = (
    ("Conservative", "950", "£4.2M", "£3.8M", "£0.4M"),
    ("Baseline", "1,050", "£4.8M", "£4.2M", "£0.6M"),
    ("Optimistic", "1,200", "£5.6M", "£4.8M", "£0.8M"),
)

#: Expense share of revenue used when no expense ledger is available.
EXPENSE_RATIO_ESTIMATE = 0.7


# --------------------------------------------------------------------------- #
# Historical series
# --------------------------------------------------------------------------- #
def monthly_revenue_history(months: int = 12, completed_only: bool = True) -> list[tuple[str, float]]:
    """Monthly payment totals for the last *months* months, oldest first."""
    status_clause = "AND status = 'completed'" if completed_only else ""
    conn = get_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT strftime('%Y-%m', payment_date) AS ym, COALESCE(SUM(amount), 0)
            FROM payments
            WHERE payment_date >= date('now', ?)
              {status_clause}
            GROUP BY ym
            ORDER BY ym
            """,
            (f"-{int(months)} months",),
        ).fetchall()
    finally:
        conn.close()
    return [(str(r[0]), float(r[1] or 0)) for r in rows if r[0]]


def monthly_expense_history(months: int = 12) -> list[tuple[str, float]]:
    """Monthly purchase-order spend for the last *months* months, oldest first.

    Reads the ``finance_purchase_orders`` table owned by
    ``domain/operations_service.py`` (``net_amount`` dated by ``created_at``).
    """
    conn = get_connection()
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='finance_purchase_orders'"
        ).fetchone()
        if not exists:
            return []
        rows = conn.execute(
            """
            SELECT strftime('%Y-%m', created_at) AS ym, COALESCE(SUM(net_amount), 0)
            FROM finance_purchase_orders
            WHERE status IN ('approved', 'ordered', 'received', 'closed')
              AND created_at >= date('now', ?)
            GROUP BY ym
            ORDER BY ym
            """,
            (f"-{int(months)} months",),
        ).fetchall()
    finally:
        conn.close()
    return [(str(r[0]), float(r[1] or 0)) for r in rows if r[0]]


# --------------------------------------------------------------------------- #
# Simple growth forecast (Analytics tab "Generate Forecast")
# --------------------------------------------------------------------------- #
def simple_growth_forecast(months: int = 12, growth_rate: float = 0.05) -> dict[str, Any]:
    """Compound a baseline monthly revenue forward by *growth_rate* per month.

    Baseline is the mean of the last 12 monthly payment totals (all statuses,
    matching the GUI).  Returns ``{"baseline", "growth_rate", "projections",
    "total"}`` where projections is a list of ``(YYYY-MM, amount)``.
    """
    months = max(1, int(months))
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT strftime('%Y-%m', payment_date) AS ym, COALESCE(SUM(amount), 0)
            FROM payments
            GROUP BY ym
            ORDER BY ym DESC
            LIMIT 12
            """
        ).fetchall()
    finally:
        conn.close()
    baseline = (sum(float(r[1]) for r in rows) / len(rows)) if rows else 0.0

    projections: list[tuple[str, float]] = []
    value = baseline
    first_of_month = datetime.now().replace(day=1)
    for i in range(1, months + 1):
        value = value * (1 + growth_rate)
        month = (first_of_month + timedelta(days=31 * i)).replace(day=1)
        projections.append((month.strftime("%Y-%m"), round(value, 2)))

    return {
        "baseline": round(baseline, 2),
        "growth_rate": growth_rate,
        "projections": projections,
        "total": round(sum(a for _, a in projections), 2),
    }


# --------------------------------------------------------------------------- #
# Forecast summary cards (Forecasting tab "Refresh")
# --------------------------------------------------------------------------- #
def forecast_summary(horizon_months: int = 6) -> dict[str, float]:
    """Headline projection figures: revenue, expenses, collections, net."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT AVG(monthly_total) * ?
            FROM (
                SELECT strftime('%Y-%m', created_at) AS month, SUM(amount) AS monthly_total
                FROM payments
                WHERE created_at >= date('now', '-12 months')
                GROUP BY month
            )
            """,
            (int(horizon_months),),
        ).fetchone()
        projected_revenue = float(row[0] or 0) if row else 0.0

        row = conn.execute(
            """
            SELECT SUM(total_debt - amount_collected)
            FROM collection_cases
            WHERE case_status IN ('new', 'assigned', 'in_progress')
            """
        ).fetchone()
        expected_collections = float(row[0] or 0) if row else 0.0
    finally:
        conn.close()

    projected_expenses = projected_revenue * EXPENSE_RATIO_ESTIMATE
    return {
        "horizon_months": horizon_months,
        "projected_revenue": round(projected_revenue, 2),
        "projected_expenses": round(projected_expenses, 2),
        "expected_collections": round(expected_collections, 2),
        "net_projection": round(projected_revenue - projected_expenses, 2),
    }


def forecast_summary_text(summary: dict[str, float] | None = None) -> str:
    """Plain-text rendering of :func:`forecast_summary`."""
    s = summary or forecast_summary()
    horizon = s.get("horizon_months", 6)
    lines = [
        f"Forecasting Data Updated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "=" * 70,
        "",
        f"{horizon}-Month Revenue Projection: £{s['projected_revenue']:,.2f}",
        f"{horizon}-Month Expense Projection: £{s['projected_expenses']:,.2f}",
        f"Expected Collections: £{s['expected_collections']:,.2f}",
        f"Net Projection: £{s['net_projection']:,.2f}",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# "Generate Forecast" narrative (Forecasting tab)
# --------------------------------------------------------------------------- #
def generate_forecast_text(forecast_months: int = 6) -> str:
    """Average-based revenue forecast with the GUI's assumptions block."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT AVG(monthly_revenue)
            FROM (
                SELECT strftime('%Y-%m', created_at) AS month, SUM(amount) AS monthly_revenue
                FROM payments
                WHERE created_at >= date('now', '-12 months')
                GROUP BY month
            )
            """
        ).fetchone()
    finally:
        conn.close()
    avg_revenue = float(row[0] or 0) if row else 0.0
    projected_revenue = avg_revenue * forecast_months

    return "\n".join(
        [
            f"Financial Forecast Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
            "=" * 70,
            "",
            f"Forecast Period: {forecast_months} months",
            "Based on: 12 months historical data",
            "",
            f"Projected Revenue: £{projected_revenue:,.2f}",
            f"Average Monthly Revenue: £{avg_revenue:,.2f}",
            "",
            "Assumptions:",
            "- Student enrollment remains stable",
            "- Fee structure unchanged",
            "- Collection rate at historical average",
            "",
            "Recommendations:",
            "- Monitor actual vs. forecast monthly",
            "- Adjust for seasonal variations",
            "- Review collection strategies",
            "",
        ]
    )


# --------------------------------------------------------------------------- #
# Revenue / expense projection reports (moving average + growth trend)
# --------------------------------------------------------------------------- #
def project_series(series: list[tuple[str, float]]) -> dict[str, Any]:
    """Moving-average projection with a first-vs-last quarter growth trend.

    Mirrors the GUI arithmetic exactly: recent average = mean of the last three
    months; growth = (last 3 − first 3) / first 3 when ≥ 6 months exist; the
    growth factor is applied in full to 3 months, √ to 6 months and ⁴√ to 12.
    """
    total = sum(v for _, v in series)
    avg_monthly = total / len(series) if series else 0.0
    recent = series[-3:] if len(series) >= 3 else series
    recent_avg = (sum(v for _, v in recent) / len(recent)) if recent else 0.0

    growth_rate = 0.0
    if len(series) >= 6:
        first_half = sum(v for _, v in series[:3])
        second_half = sum(v for _, v in series[-3:])
        growth_rate = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0.0

    proj_3, proj_6, proj_12 = recent_avg * 3, recent_avg * 6, recent_avg * 12
    if growth_rate:
        factor = 1 + growth_rate / 100
        proj_3 *= factor
        proj_6 *= factor**0.5
        proj_12 *= factor**0.25

    return {
        "series": series,
        "total": round(total, 2),
        "avg_monthly": round(avg_monthly, 2),
        "recent_avg": round(recent_avg, 2),
        "growth_rate": round(growth_rate, 2),
        "next_3_months": round(proj_3, 2),
        "next_6_months": round(proj_6, 2),
        "next_12_months": round(proj_12, 2),
    }


def _projection_report(title: str, label: str, projection: dict[str, Any]) -> str:
    series = projection["series"]
    out = ["=" * 80, title, "=" * 80, "", f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}", ""]
    if not series:
        out.append(f"No historical {label.lower()} data available for projection.")
        return "\n".join(out) + "\n"

    out += [f"HISTORICAL {label.upper()} (Last 12 Months):", "-" * 80,
            f"{'Month':<15} {label:>20}", "-" * 80]
    out += [f"{month:<15} £{value:>18,.2f}" for month, value in series]
    out += ["-" * 80,
            f"{'Total ' + label:<15} £{projection['total']:>18,.2f}",
            f"{'Average/Month':<15} £{projection['avg_monthly']:>18,.2f}", "",
            f"{label.upper()} PROJECTIONS:", "-" * 80]
    if len(series) >= 6:
        out += [f"Growth Trend: {projection['growth_rate']:+.2f}%", ""]
    out += [f"Next 3 Months:  £{projection['next_3_months']:,.2f}",
            f"Next 6 Months:  £{projection['next_6_months']:,.2f}",
            f"Next 12 Months: £{projection['next_12_months']:,.2f}", "",
            "Note: Projections based on historical trends and simple moving averages."]
    return "\n".join(out) + "\n"


def revenue_projection() -> dict[str, Any]:
    """Projection over the last 12 months of completed payments."""
    return project_series(monthly_revenue_history(12))


def revenue_projection_report() -> str:
    return _projection_report("REVENUE PROJECTION ANALYSIS", "Revenue", revenue_projection())


def expense_projection() -> dict[str, Any]:
    """Projection over the last 12 months of approved purchase-order spend."""
    return project_series(monthly_expense_history(12))


def expense_projection_report() -> str:
    return _projection_report("EXPENSE PROJECTION ANALYSIS", "Expenses", expense_projection())


# --------------------------------------------------------------------------- #
# Scenario planning narrative (Analytics manager)
# --------------------------------------------------------------------------- #
def scenario_planning_text() -> str:
    """Static three-scenario planning narrative used by the GUI scenarios tab."""
    bar = "=" * 60
    now = datetime.now()
    return f"""Financial Scenario Planning Analysis
{bar}
Generated on: {now:%Y-%m-%d %H:%M:%S}

SCENARIO ASSUMPTIONS:
{bar}

Conservative Scenario:
- Student enrollment: 950 (-9.5% from baseline)
- Tuition increase: 2%
- Operating cost increase: 4%
- Financial aid budget: Maintained at current level

Baseline Scenario:
- Student enrollment: 1,050 (current projection)
- Tuition increase: 3%
- Operating cost increase: 3%
- Financial aid budget: 5% increase

Optimistic Scenario:
- Student enrollment: 1,200 (+14.3% from baseline)
- Tuition increase: 4%
- Operating cost increase: 2.5%
- Financial aid budget: 10% increase

FINANCIAL PROJECTIONS:
{bar}

Conservative Scenario:
- Tuition Revenue: £4,200,000
- Total Revenue: £4,200,000
- Operating Expenses: £3,800,000
- Net Income: £400,000
- Cash Flow: Positive but tight

Baseline Scenario:
- Tuition Revenue: £4,800,000
- Total Revenue: £4,800,000
- Operating Expenses: £4,200,000
- Net Income: £600,000
- Cash Flow: Healthy growth

Optimistic Scenario:
- Tuition Revenue: £5,600,000
- Total Revenue: £5,600,000
- Operating Expenses: £4,800,000
- Net Income: £800,000
- Cash Flow: Strong growth potential

RISK FACTORS:
{bar}

Conservative Scenario Risks:
- Enrollment decline may continue
- Competition from other institutions
- Economic downturn affecting student ability to pay

Baseline Scenario Risks:
- Market saturation in target demographics
- Regulatory changes in education funding
- Technology disruption requiring additional investment

Optimistic Scenario Risks:
- Overextension of resources
- Quality maintenance with rapid growth
- Infrastructure capacity limitations

RECOMMENDATIONS:
{bar}

1. Diversify revenue streams beyond tuition
2. Implement flexible cost management strategies
3. Develop contingency plans for each scenario
4. Monitor key performance indicators monthly
5. Maintain strategic reserves for unexpected challenges

Next Review Date: {(now + timedelta(days=90)):%Y-%m-%d}
"""


# --------------------------------------------------------------------------- #
# Dashboard datasets (Analytics tab charts)
# --------------------------------------------------------------------------- #
def dashboard_datasets(year: int | None = None) -> dict[str, list[tuple]]:
    """The four datasets the Analytics dashboard charts are drawn from.

    Returns ``{"monthly_revenue": [(month, revenue)],
    "payment_methods": [(method, count, amount)],
    "outstanding_by_course": [(course, outstanding)],
    "payment_plan_status": [(status, count, total)]}``.
    """
    year_str = str(year or datetime.now().year)
    conn = get_connection()
    try:
        monthly = conn.execute(
            """
            SELECT strftime('%m', payment_date) AS month, SUM(amount)
            FROM payments
            WHERE strftime('%Y', payment_date) = ? AND status = 'completed'
            GROUP BY month ORDER BY month
            """,
            (year_str,),
        ).fetchall()
        methods = conn.execute(
            """
            SELECT payment_method, COUNT(*), SUM(amount)
            FROM payments
            WHERE strftime('%Y', payment_date) = ? AND status = 'completed'
            GROUP BY payment_method ORDER BY SUM(amount) DESC
            """,
            (year_str,),
        ).fetchall()
        outstanding = conn.execute(
            """
            SELECT s.course, SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) AS outstanding
            FROM student_fees sf
            JOIN students s ON sf.student_id = s.student_id
            LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
            WHERE sf.status IN ('unpaid', 'partial')
            GROUP BY s.course
            HAVING outstanding > 0
            ORDER BY outstanding DESC
            LIMIT 10
            """
        ).fetchall()
        plans = conn.execute(
            "SELECT status, COUNT(*), SUM(total_amount) FROM student_payment_plans GROUP BY status"
        ).fetchall()
    finally:
        conn.close()

    return {
        "monthly_revenue": [(str(r[0]), float(r[1] or 0)) for r in monthly],
        "payment_methods": [(str(r[0] or "unknown"), int(r[1] or 0), float(r[2] or 0)) for r in methods],
        "outstanding_by_course": [(str(r[0] or "unknown"), float(r[1] or 0)) for r in outstanding],
        "payment_plan_status": [(str(r[0] or "unknown"), int(r[1] or 0), float(r[2] or 0)) for r in plans],
    }


__all__ = [
    "EXPENSE_RATIO_ESTIMATE",
    "SCENARIO_COMPARISON_ROWS",
    "dashboard_datasets",
    "expense_projection",
    "expense_projection_report",
    "forecast_summary",
    "forecast_summary_text",
    "generate_forecast_text",
    "monthly_expense_history",
    "monthly_revenue_history",
    "project_series",
    "revenue_projection",
    "revenue_projection_report",
    "scenario_planning_text",
    "simple_growth_forecast",
]
