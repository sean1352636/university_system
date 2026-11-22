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


# --------------------------------------------------------------------------- #
# Linear-trend forecast with a back-test (Advanced Financial Forecasting)
# --------------------------------------------------------------------------- #
#: Fewest complete months a trend is fitted to.
MIN_TREND_MONTHS = 3
#: Months held out, one at a time, to measure the forecast's error.
BACKTEST_MONTHS = 3


def _next_month(ym: str) -> str:
    year, month = int(ym[:4]), int(ym[5:7])
    return f"{year + month // 12}-{month % 12 + 1:02d}"


def complete_monthly_series(history: list[tuple[str, float]],
                            through: str | None = None) -> list[tuple[str, float]]:
    """*history* with months that had no payments filled in as 0.

    Runs from the first month in *history* to *through* (default: last
    month, so the current part-month never drags the trend down).
    """
    if through is None:
        through = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    totals = {ym: v for ym, v in history if ym <= through}
    if not totals:
        return []
    series, ym = [], min(totals)
    while ym <= through:
        series.append((ym, float(totals.get(ym, 0.0))))
        ym = _next_month(ym)
    return series


def _fit_line(values: list[float]) -> tuple[float, float]:
    """Least-squares (intercept, slope) of *values* against 0..n-1."""
    n = len(values)
    mean_x, mean_y = (n - 1) / 2, sum(values) / n
    sxx = sum((x - mean_x) ** 2 for x in range(n))
    slope = (sum((x - mean_x) * (y - mean_y) for x, y in enumerate(values)) / sxx) if sxx else 0.0
    return mean_y - slope * mean_x, slope


def trend_forecast(series: list[tuple[str, float]], horizon: int = 12,
                   window: int = 12) -> dict[str, Any]:
    """Forecast *horizon* months from a linear trend over the last *window* months.

    Accuracy comes from a back-test: each of the last ``BACKTEST_MONTHS``
    months is forecast from the months before it only and compared with what
    actually came in. ``accuracy`` is 100 − WAPE (weighted absolute % error);
    ``rmse`` gives the ±1.96·RMSE monthly range. Either is ``None`` when there
    is too little history, with the reason in ``notes`` — nothing is guessed.
    """
    result: dict[str, Any] = {
        "months_used": 0, "slope": None, "projections": [], "total": None,
        "accuracy": None, "wape": None, "rmse": None, "backtest": [], "notes": [],
    }
    if len(series) < MIN_TREND_MONTHS:
        result["notes"].append(
            f"Only {len(series)} complete month(s) of payments; a trend needs at least "
            f"{MIN_TREND_MONTHS}. No forecast made.")
        return result

    fit = series[-window:]
    values = [v for _, v in fit]
    intercept, slope = _fit_line(values)
    result["months_used"] = len(fit)
    result["slope"] = round(slope, 2)
    ym = fit[-1][0]
    for i in range(horizon):
        ym = _next_month(ym)
        # Revenue cannot go negative; a falling trend bottoms out at zero.
        result["projections"].append((ym, round(max(0.0, intercept + slope * (len(fit) + i)), 2)))
    result["total"] = round(sum(v for _, v in result["projections"]), 2)

    if len(series) < MIN_TREND_MONTHS + BACKTEST_MONTHS:
        result["notes"].append(
            f"Accuracy not measured: back-testing {BACKTEST_MONTHS} months needs at least "
            f"{MIN_TREND_MONTHS + BACKTEST_MONTHS} complete months (have {len(series)}).")
        return result

    abs_err = actual_sum = sq_err = 0.0
    for k in range(len(series) - BACKTEST_MONTHS, len(series)):
        train = [v for _, v in series[max(0, k - window):k]]
        b0, b1 = _fit_line(train)
        predicted = max(0.0, b0 + b1 * len(train))
        actual = series[k][1]
        result["backtest"].append((series[k][0], round(predicted, 2), round(actual, 2)))
        abs_err += abs(predicted - actual)
        sq_err += (predicted - actual) ** 2
        actual_sum += actual
    result["rmse"] = round((sq_err / BACKTEST_MONTHS) ** 0.5, 2)
    if actual_sum > 0:
        result["wape"] = round(100 * abs_err / actual_sum, 1)
        result["accuracy"] = round(max(0.0, 100 - result["wape"]), 1)
    else:
        result["notes"].append("Accuracy not measured: no payments in the back-test months.")
    return result


# --------------------------------------------------------------------------- #
# Budget vs actual (Comprehensive Budget Variance Report)
# --------------------------------------------------------------------------- #
def _academic_year_start(today: datetime | None = None) -> int:
    today = today or datetime.now()
    return today.year if today.month >= 9 else today.year - 1


def budget_variance(conn=None) -> dict[str, Any]:
    """Budget against actual, per category, for the current budget plan.

    The plan is the one for the current academic year (``2026-2027`` or
    ``2026/2027``), else the most recent plan. Budgets are the plan's
    ``budget_line_items``. Revenue actuals are completed payments dated in
    the plan's academic year (1 Sep - 31 Aug), read live and shown as one
    revenue line (payments carry no category); expense actuals
    are the ``actual_amount`` kept on the line items by Budget Management,
    as no categorised expense ledger exists. Returns ``{"plan": None, "rows":
    []}`` when no plan has line items — nothing is invented.
    """
    own = conn is None
    conn = conn or get_connection()
    try:
        start = _academic_year_start()
        plans = conn.execute(
            """
            SELECT bp.budget_id, bp.plan_name, bp.academic_year
            FROM budget_plans bp
            WHERE EXISTS (SELECT 1 FROM budget_line_items bli WHERE bli.budget_id = bp.budget_id)
            ORDER BY bp.academic_year IN (?, ?) DESC, bp.budget_id DESC
            LIMIT 1
            """,
            (f"{start}-{start + 1}", f"{start}/{start + 1}"),
        ).fetchall()
        if not plans:
            return {"plan": None, "rows": []}
        budget_id, plan_name, plan_year = tuple(plans[0])
        try:
            year_start = int(str(plan_year or "")[:4])
        except ValueError:
            year_start = start
        window = (f"{year_start}-09-01", f"{year_start + 1}-09-01")
        revenue_actual = float(conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'completed' "
            "AND payment_date >= ? AND payment_date < ?", window).fetchone()[0] or 0)
        rows = conn.execute(
            """
            SELECT bc.category_name, COALESCE(bc.category_type, ''),
                   COALESCE(SUM(bli.budgeted_amount), 0), COALESCE(SUM(bli.actual_amount), 0)
            FROM budget_line_items bli
            JOIN budget_categories bc ON bli.category_id = bc.category_id
            WHERE bli.budget_id = ?
            GROUP BY bc.category_id
            ORDER BY 3 DESC
            """,
            (budget_id,),
        ).fetchall()
    finally:
        if own:
            conn.close()

    # Payments are not categorised, so revenue is one line: every revenue
    # category's budget against all completed payments in the year.
    out = []
    revenue_budget = sum(float(r[2] or 0) for r in rows if str(r[1]).lower() == "revenue")
    if any(str(r[1]).lower() == "revenue" for r in rows):
        out.append(("Revenue (all categories)", "revenue", round(revenue_budget, 2),
                    round(revenue_actual, 2)))
    for name, kind, budgeted, stored_actual in rows:
        if str(kind).lower() != "revenue":
            out.append((str(name), str(kind).lower(), round(float(budgeted or 0), 2),
                        round(float(stored_actual or 0), 2)))
    return {"plan": {"budget_id": budget_id, "name": plan_name, "academic_year": plan_year,
                     "window": window, "revenue_actual": round(revenue_actual, 2)},
            "rows": out}


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
