"""
Revenue by Source — interactive CLI.

Command-line twin of the Finance GUI "Revenue by Source" tab
(``interfaces/gui/finance/revenue_source_manager.py``).  Both call the same
``domain/reporting/revenue_by_source_report`` functions against the shared
``student_records.db``.

Covers: breakdown by source for a date range (count / total / average / min /
max / percentage with totals), monthly trend for one source, period-to-period
comparison, CSV export, and — when matplotlib is installed — saving the pie,
bar and trend charts as PNG files.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from education_system.systems.university.domains.finance.domain.reporting.revenue_by_source_report import (
    compare_source_revenue_periods,
    export_revenue_by_source_csv,
    get_revenue_by_source,
    get_source_revenue_trend,
)
from education_system.systems.university.domains.finance.interfaces.cli.support import (
    header,
    money,
    offer_chart,
    print_table,
    prompt,
    prompt_bool,
    prompt_choice,
    prompt_date,
    prompt_int,
    require_finance_access,
    run_menu,
    text,
)

logger = logging.getLogger(__name__)

#: Last loaded breakdown, so charts/trends reuse it like the GUI does.
_state: dict[str, Any] = {"start": "", "end": "", "data": {}}


def _default_dates() -> tuple[str, str]:
    today = datetime.now()
    return (today - timedelta(days=365)).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


def _ask_dates(allow_blank: bool = False) -> tuple[str, str]:
    start_default, end_default = _default_dates()
    start = prompt_date(text("finance_cli.revenue.start_date", "Start date (YYYY-MM-DD)"),
                        _state["start"] or start_default, allow_blank=allow_blank)
    end = prompt_date(text("finance_cli.revenue.end_date", "End date (YYYY-MM-DD)"),
                      _state["end"] or end_default, allow_blank=allow_blank)
    return start, end


def _sorted_sources(data: dict[str, dict[str, float]]) -> list[tuple[str, dict[str, float]]]:
    return sorted(data.items(), key=lambda item: item[1]["total"], reverse=True)


# --------------------------------------------------------------------------- #
# 1-2. Breakdown
# --------------------------------------------------------------------------- #
def _show_breakdown(start: str | None, end: str | None) -> None:
    data = get_revenue_by_source(start or None, end or None)
    _state.update(start=start or "", end=end or "", data=data)
    header(text("finance_cli.revenue.breakdown_title", "REVENUE BREAKDOWN BY SOURCE"), 80)
    period = f"{start} → {end}" if start and end else text("finance_cli.revenue.all_time", "All time")
    print(text("finance_cli.revenue.period", "Period: {period}", period=period))
    if not data:
        print(text("finance_cli.revenue.no_data", "No revenue data found for the specified period."))
        return

    total_revenue = sum(d["total"] for d in data.values())
    total_count = sum(d["count"] for d in data.values())
    rows = []
    for source, d in _sorted_sources(data):
        pct = (d["total"] / total_revenue * 100) if total_revenue > 0 else 0.0
        rows.append((source, d["count"], money(d["total"]), money(d["average"]),
                     money(d["min"]), money(d["max"]), f"{pct:.1f}%"))
    print()
    print_table(("Source", "Count", "Total", "Average", "Min", "Max", "%"), rows,
                align=("<", ">", ">", ">", ">", ">", ">"))
    print("-" * 80)
    print(text("finance_cli.revenue.summary",
               "Total: {total} | Transactions: {count}",
               total=money(total_revenue), count=f"{total_count:,}"))


def _breakdown_range() -> None:
    start, end = _ask_dates()
    _show_breakdown(start, end)


def _breakdown_all_time() -> None:
    _show_breakdown(None, None)


# --------------------------------------------------------------------------- #
# 3. Trend
# --------------------------------------------------------------------------- #
def _pick_source() -> str | None:
    sources = [s for s, _ in _sorted_sources(_state["data"])]
    if sources:
        return prompt_choice(text("finance_cli.revenue.select_source", "Source"), sources, sources[0])
    name = prompt(text("finance_cli.revenue.source_name", "Source name (e.g. Library, Housing, Shop)"))
    return name or None


def _trend() -> None:
    source = _pick_source()
    if not source:
        print(text("finance_cli.revenue.source_required", "A source is required."))
        return
    months = prompt_int(text("finance_cli.revenue.months", "Number of months"), 12, minimum=1)
    trend = get_source_revenue_trend(source, months)
    header(text("finance_cli.revenue.trend_title", "{source} REVENUE TREND (LAST {months} MONTHS)",
                source=source.upper(), months=months), 80)
    if not trend:
        print(text("finance_cli.revenue.no_trend", "No trend data available for {source}.",
                   source=source))
        return
    ordered = list(reversed(trend))  # oldest first, as the GUI plots it
    print_table(("Month", "Revenue", "Transactions"),
                [(m, money(rev), count) for m, rev, count in ordered], align=("<", ">", ">"))
    print("-" * 80)
    print(text("finance_cli.revenue.trend_total", "Total: {total} over {n} month(s)",
               total=money(sum(r for _, r, _ in ordered)), n=len(ordered)))
    offer_chart(f"revenue_trend_{source.replace(' ', '_').lower()}.png", "line",
                [m for m, _, _ in ordered], [r for _, r, _ in ordered],
                f"{source} - Monthly Revenue Trend", "Revenue (£)",
                secondary=[c for _, _, c in ordered], secondary_label="Transactions")


# --------------------------------------------------------------------------- #
# 4. Compare periods
# --------------------------------------------------------------------------- #
def _compare_periods() -> None:
    source = _pick_source()
    if not source:
        print(text("finance_cli.revenue.source_required", "A source is required."))
        return
    print("\n" + text("finance_cli.revenue.period_1", "Period 1"))
    p1_start = prompt_date("  " + text("finance_cli.revenue.start_date", "Start date (YYYY-MM-DD)"))
    p1_end = prompt_date("  " + text("finance_cli.revenue.end_date", "End date (YYYY-MM-DD)"))
    print("\n" + text("finance_cli.revenue.period_2", "Period 2"))
    p2_start = prompt_date("  " + text("finance_cli.revenue.start_date", "Start date (YYYY-MM-DD)"))
    p2_end = prompt_date("  " + text("finance_cli.revenue.end_date", "End date (YYYY-MM-DD)"))

    comparison = compare_source_revenue_periods(source, p1_start, p1_end, p2_start, p2_end)
    if not comparison:
        print(text("finance_cli.revenue.compare_failed", "Comparison could not be produced."))
        return
    p1, p2, ch = comparison["period1"], comparison["period2"], comparison["changes"]
    header(text("finance_cli.revenue.compare_title", "{source} REVENUE COMPARISON",
                source=source.upper()))
    print_table(
        ("Period", "From", "To", "Transactions", "Revenue"),
        [("1", p1["start"], p1["end"], p1["transactions"], money(p1["revenue"])),
         ("2", p2["start"], p2["end"], p2["transactions"], money(p2["revenue"]))],
        align=("<", "<", "<", ">", ">"),
    )
    print()
    print(text("finance_cli.revenue.change_count", "Transaction change: {count:+,} ({pct:+.1f}%)",
               count=ch["transaction_count"], pct=ch["transaction_pct"]))
    print(text("finance_cli.revenue.change_revenue", "Revenue change: £{amount:+,.2f} ({pct:+.1f}%)",
               amount=ch["revenue_amount"], pct=ch["revenue_pct"]))


# --------------------------------------------------------------------------- #
# 5. Charts
# --------------------------------------------------------------------------- #
def _charts() -> None:
    data = _state["data"]
    if not data:
        print(text("finance_cli.revenue.load_first", "Load a breakdown first (option 1 or 2)."))
        return
    ordered = _sorted_sources(data)
    labels = [s for s, _ in ordered]
    totals = [d["total"] for _, d in ordered]
    stamp = datetime.now().strftime("%Y%m%d")
    print(text("finance_cli.revenue.charts_intro",
               "Charts reproduce the GUI pie (share of revenue) and bar (revenue by source)."))
    offer_chart(f"revenue_by_source_pie_{stamp}.png", "pie", labels, totals,
                "Revenue Distribution by Source")
    offer_chart(f"revenue_by_source_bar_{stamp}.png", "bar", labels, totals,
                "Revenue by Source", "Revenue (£)")


# --------------------------------------------------------------------------- #
# 6. Export
# --------------------------------------------------------------------------- #
def _export_csv() -> None:
    filename = prompt(text("finance_cli.revenue.csv_filename", "CSV filename"),
                      f"revenue_by_source_{datetime.now():%Y%m%d}.csv")
    start = end = None
    if prompt_bool(text("finance_cli.revenue.filter_dates", "Filter by date range?"),
                   bool(_state["start"])):
        start, end = _ask_dates()
    if export_revenue_by_source_csv(filename, start, end):
        print(text("finance_cli.revenue.export_success", "Revenue data exported to {filename}",
                   filename=filename))
    else:
        print(text("finance_cli.revenue.export_failed", "Export failed."))


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_revenue_menu(auth) -> None:
    """Run the Revenue by Source CLI loop (admin and staff)."""
    if not require_finance_access(auth):
        return
    run_menu(
        text("finance_cli.revenue.title", "REVENUE BY SOURCE"),
        (
            (text("finance_cli.revenue.opt_range", "Revenue breakdown for a date range"),
             _breakdown_range),
            (text("finance_cli.revenue.opt_all", "Revenue breakdown (all time)"), _breakdown_all_time),
            (text("finance_cli.revenue.opt_trend", "Monthly trend for a source"), _trend),
            (text("finance_cli.revenue.opt_compare", "Compare two periods for a source"),
             _compare_periods),
            (text("finance_cli.revenue.opt_charts", "Save breakdown charts as PNG"), _charts),
            (text("finance_cli.revenue.opt_export", "Export breakdown to CSV"), _export_csv),
        ),
    )


__all__ = ["run_revenue_menu"]
