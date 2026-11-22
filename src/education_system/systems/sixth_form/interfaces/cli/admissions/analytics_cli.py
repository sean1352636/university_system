"""Admissions CLI: analytics, reports and CSV import/export."""

from __future__ import annotations

from datetime import date as _date
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)
from education_system.systems.sixth_form.domain.admissions import (
    applicant_reports as reports,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    STATUSES,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _UserAbort,
    _forecast_enrolment,
    _input,
    _pause,
    _pick_from,
    _print_applicants,
    _yes,
)



def _write_summary_pdf(path: str) -> None:
    """Management summary PDF: headline + funnel + source effectiveness."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )
    from education_system.platform import branding
    styles = getSampleStyleSheet()
    summ = reports.summary()
    elems = [Paragraph(f"{branding.SYSTEM_NAME} — Admissions summary",
                       styles["Title"]),
             Paragraph(f"Generated {_date.today().isoformat()}",
                       styles["Normal"]), Spacer(1, 10),
             Paragraph("Headline", styles["Heading2"])]
    head = [["Total", summ.total], ["Open", summ.open_count],
            ["Awaiting decision", summ.awaiting_decision],
            ["Pending offers", summ.pending_offers],
            ["Converted", summ.converted], ["Rejected", summ.rejected]]
    t1 = Table(head, colWidths=[6 * cm, 3 * cm])
    t1.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                            ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    elems += [t1, Spacer(1, 10),
              Paragraph("Conversion funnel", styles["Heading2"])]
    funnel_rows = [["Stage", "Count"]] + [[s, n] for s, n in reports.funnel()]
    t2 = Table(funnel_rows, colWidths=[7 * cm, 3 * cm], repeatRows=1)
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b63")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    elems += [t2, Spacer(1, 10),
              Paragraph("Source effectiveness", styles["Heading2"])]
    src_rows = [["Source", "Total", "Offers", "Enrolled", "Conv%"]]
    for d in reports.source_effectiveness():
        src_rows.append([d["source"], d["total"], d["offers"],
                         d["enrolled"], f"{d['conversion']}%"])
    t3 = Table(src_rows, repeatRows=1,
               colWidths=[5 * cm, 2 * cm, 2 * cm, 2.5 * cm, 2 * cm])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b63")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    elems.append(t3)
    SimpleDocTemplate(path, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                      topMargin=2 * cm, bottomMargin=2 * cm).build(elems)


# ── Analytics (items 41–46) ───────────────────────────────────────

def analytics_flow() -> None:
    print("\n═══ Admissions Analytics ═══")
    fn = reports.funnel()
    top = fn[0][1] if fn else 0
    print("\n  Conversion funnel:")
    for stage, n in fn:
        bar = "█" * (round(30 * n / top) if top else 0)
        pct = f"{round(100 * n / top)}%" if top else "—"
        print(f"    {stage:<20} {n:>4} {pct:>4}  {bar}")

    print("\n  Source effectiveness:")
    print(f"    {'Source':<18}{'Total':>6}{'Offers':>8}"
          f"{'Enrolled':>10}{'Conv%':>8}")
    for d in reports.source_effectiveness():
        print(f"    {d['source']:<18}{d['total']:>6}{d['offers']:>8}"
              f"{d['enrolled']:>10}{d['conversion']:>7}%")

    ttd = reports.time_to_decision_stats()
    print("\n  Time to decision (days):")
    if ttd["count"]:
        print(f"    n={ttd['count']}  avg={ttd['avg']}  "
              f"median={ttd['median']}  min={ttd['min']}  max={ttd['max']}")
    else:
        print("    (no decisions yet)")

    print("\n  Applications by week:")
    weeks = reports.applications_by_week()[-10:]
    wmax = max((n for _, n in weeks), default=0)
    for wk, n in weeks:
        print(f"    {wk:<10} {n:>4} {'█' * (round(20 * n / wmax) if wmax else 0)}")
    if not weeks:
        print("    (none)")

    print("\n  Subject demand:")
    for subj, n in reports.subject_demand()[:15]:
        print(f"    {subj:<28} {n:>4}")

    # Drill-down (item 46).
    if _yes("\n  Drill down into a status?"):
        status = _pick_from("Status", list(STATUSES))
        _print_applicants(data.list_applicants(status=status))
    _pause()


# ── CSV import / export (items 47, 48) ────────────────────────────

def export_csv_flow() -> None:
    print("\n═══ Export Applicants to CSV ═══")
    path = _input("Save to path", default="applicants.csv")
    try:
        n = reports.export_csv(path)
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ Exported {n} applicant(s) to {path}")
    _pause()


def import_csv_flow() -> None:
    print("\n═══ Import Applicants from CSV ═══")
    path = _input("CSV path", allow_empty=False)
    try:
        created, errors = reports.import_csv(path)
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ Imported {created} applicant(s).")
    for err in errors[:12]:
        print(f"    ✗ {err}")
    if len(errors) > 12:
        print(f"    … and {len(errors) - 12} more.")
    _pause()


# ══ Analytics flows (GUI items 26–35) ═════════════════════════════

def funnel_report_flow() -> None:
    """Item 26 — conversion funnel."""
    print("\n═══ Conversion Funnel ═══")
    fn = reports.funnel()
    top = fn[0][1] if fn else 0
    for stage, n in fn:
        bar = "█" * (round(30 * n / top) if top else 0)
        pct = f"{round(100 * n / top)}%" if top else "—"
        print(f"    {stage:<20} {n:>4} {pct:>4}  {bar}")
    if not fn:
        print("    (no data)")
    _pause()


def source_report_flow() -> None:
    """Item 27 — source effectiveness."""
    print("\n═══ Source Effectiveness ═══")
    print(f"    {'Source':<18}{'Total':>6}{'Offers':>8}"
          f"{'Enrolled':>10}{'Conv%':>8}")
    for d in reports.source_effectiveness():
        print(f"    {d['source']:<18}{d['total']:>6}{d['offers']:>8}"
              f"{d['enrolled']:>10}{d['conversion']:>7}%")
    _pause()


def weekly_trend_flow() -> None:
    """Item 28 — applications by week."""
    print("\n═══ Applications by Week ═══")
    weeks = reports.applications_by_week()[-12:]
    wmax = max((n for _, n in weeks), default=0)
    for wk, n in weeks:
        bar = "█" * (round(24 * n / wmax) if wmax else 0)
        print(f"    {wk:<10} {n:>4}  {bar}")
    if not weeks:
        print("    (no applications)")
    _pause()


def subject_demand_flow() -> None:
    """Item 29 — subject demand."""
    print("\n═══ Subject Demand ═══")
    rows = reports.subject_demand()
    dmax = rows[0][1] if rows else 0
    for subj, n in rows[:20]:
        bar = "█" * (round(24 * n / dmax) if dmax else 0)
        print(f"    {subj:<28} {n:>4}  {bar}")
    if not rows:
        print("    (no subject choices recorded)")
    _pause()


def time_to_decision_flow() -> None:
    """Item 30 — time-to-decision statistics."""
    print("\n═══ Time to Decision (days) ═══")
    ttd = reports.time_to_decision_stats()
    if ttd["count"]:
        print(f"    n={ttd['count']}  avg={ttd['avg']}  "
              f"median={ttd['median']}  min={ttd['min']}  max={ttd['max']}")
    else:
        print("    (no decisions recorded yet)")
    _pause()


def conversion_kpi_flow() -> None:
    """Item 31 — headline offer→enrol conversion."""
    print("\n═══ Conversion KPI ═══")
    apps = data.list_applicants()
    enrolled = sum(1 for a in apps if a.status == "Enrolled")
    offers = sum(1 for a in apps
                 if a.offer_type and a.offer_type != "Not Offered")
    pct = round(100 * enrolled / offers) if offers else 0
    print(f"    Offer → Enrol conversion : {pct}%")
    print(f"    Enrolled                 : {enrolled}")
    print(f"    Offers made              : {offers}")
    _pause()


def cohort_compare_flow() -> None:
    """Item 32 — compare cohorts by application year."""
    print("\n═══ Cohort Comparison ═══")
    by_year: dict[str, dict[str, int]] = {}
    for a in data.list_applicants():
        year = (a.submitted_at or "????")[:4]
        d = by_year.setdefault(year, {"total": 0, "offers": 0,
                                      "enrolled": 0})
        d["total"] += 1
        if a.offer_type and a.offer_type != "Not Offered":
            d["offers"] += 1
        if a.status == "Enrolled":
            d["enrolled"] += 1
    print(f"\n    {'Year':<6}{'Total':>7}{'Offers':>8}"
          f"{'Enrolled':>10}{'Conv%':>8}")
    for year in sorted(by_year):
        d = by_year[year]
        conv = round(100 * d["enrolled"] / d["offers"]) if d["offers"] else 0
        print(f"    {year:<6}{d['total']:>7}{d['offers']:>8}"
              f"{d['enrolled']:>10}{conv:>7}%")
    if not by_year:
        print("    (no applicants)")
    _pause()


def export_summary_pdf_flow() -> None:
    """Item 33 — management summary PDF."""
    print("\n═══ Export Summary PDF ═══")
    path = _input("Save PDF to path", default="admissions_summary.pdf")
    try:
        _write_summary_pdf(path)
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ Saved to {path}")
    _pause()


def forecast_flow() -> None:
    """Item 34 — projected enrolment from the pipeline."""
    print("\n═══ Enrolment Forecast ═══")
    f = _forecast_enrolment(data.list_applicants())
    print(f"    Already enrolled     : {f['enrolled']}")
    print(f"    Expected additional  : {f['expected_additional']}  "
          f"(from {f['in_pipeline']} in pipeline)")
    print(f"    Projected total      : ~{f['projected_total']}")
    _pause()


def live_analytics_flow() -> None:
    """Item 35 — auto-refreshing analytics until interrupted."""
    print("\n═══ Live Analytics (Ctrl-C to stop) ═══")
    import time
    try:
        every = int(_input("Refresh every N seconds", default="30"))
    except (ValueError, _UserAbort):
        return
    try:
        while True:
            f = _forecast_enrolment(data.list_applicants())
            fn = reports.funnel()
            print(f"\n  [{_date.today().isoformat()}]  projected ~"
                  f"{f['projected_total']} enrolments")
            for stage, n in fn:
                print(f"      {stage:<20} {n}")
            time.sleep(max(1, every))
    except KeyboardInterrupt:
        print("\n  Stopped.")
