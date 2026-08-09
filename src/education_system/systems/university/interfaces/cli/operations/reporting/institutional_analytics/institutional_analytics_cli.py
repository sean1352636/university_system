"""Console menu for institutional analytics.

Style mirrors ``kpi_dashboard_cli.py``: function-based dispatch, a single
shared service instance per session, and a module-level ``auth`` set via
``set_auth`` by the launcher's new-feature dispatcher.
"""
from __future__ import annotations

from typing import Any

from education_system.systems.university.domain.operations.reporting.institutional_analytics.services.institutional_analytics_service import (  # noqa: E501
    InstitutionalAnalyticsError,
    InstitutionalAnalyticsService,
)


auth: Any = None


def set_auth(auth_object: Any) -> None:
    global auth
    auth = auth_object


def _require_login() -> bool:
    if not auth or not getattr(auth, "current_user", None):
        print("You must be logged in to access institutional analytics.")
        return False
    return True


# ---------------------------------------------------------------- formatting
def _pct(v: Any) -> str:
    return "-" if v is None else f"{v:.2f}%"


def _money(v: Any) -> str:
    if v is None:
        return "-"
    try:
        return f"£{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)


def _bar(pct: Any, width: int = 24) -> str:
    if pct is None:
        return " " * width
    filled = max(0, min(width, round(float(pct) / 100 * width)))
    return "█" * filled + "░" * (width - filled)


# ------------------------------------------------------------------- actions
def _overview(svc: InstitutionalAnalyticsService) -> None:
    data = svc.institutional_overview()
    h = data["headline"]
    print("\nInstitutional Overview")
    print("=" * 46)
    print(f"  Total students:      {h.get('total_students')}")
    print(f"  Active students:     {h.get('active_students')}")
    print(f"  Retention rate:      {_pct(h.get('retention_rate'))}")
    print(f"  Attrition rate:      {_pct(h.get('attrition_rate'))}")
    print(f"  Course fill rate:    {_pct(h.get('overall_fill_rate'))}")
    print(f"  Module pass rate:    {_pct(h.get('module_pass_rate'))}")
    print(f"  Revenue collected:   {_money(h.get('revenue_collected'))}")
    print(f"  Fees outstanding:    {_money(h.get('fees_outstanding'))}")
    if data.get("errors"):
        print("\n  Unavailable sections:")
        for name, msg in data["errors"].items():
            print(f"    - {name}: {msg}")


def _enrollment(svc: InstitutionalAnalyticsService) -> None:
    d = svc.enrollment_summary()
    print(f"\nEnrolment — {d['total_students']} students")
    print("-" * 46)
    print(f"  Current: {d['current']}   Completed: {d['completed']}   "
          f"Attrition: {d['attrition']}   Other: {d['other']}")
    print("\n  By course:")
    for row in d["by_course"]:
        print(f"    {row['label'][:30]:<30} {row['count']:>4}")


def _retention(svc: InstitutionalAnalyticsService) -> None:
    d = svc.retention_metrics()
    o = d["overall"]
    print(f"\nRetention — {d['total_students']} students")
    print("-" * 60)
    print(f"  Overall retention: {_pct(o['retention_rate'])}   "
          f"attrition: {_pct(o['attrition_rate'])}   "
          f"completion: {_pct(o['completion_rate'])}")
    print(f"\n  {'Course':<26} {'N':>4} {'Retention':>10}  Bar")
    for c in d["by_course"]:
        print(f"  {str(c['course'])[:26]:<26} {c['total']:>4} "
              f"{_pct(c['retention_rate']):>10}  {_bar(c['retention_rate'])}")


def _modules(svc: InstitutionalAnalyticsService) -> None:
    try:
        raw = input("How many top modules? (Enter for 15): ").strip()
        limit = int(raw) if raw else 15
    except ValueError:
        limit = 15
    d = svc.module_performance(limit=limit)
    t = d["totals"]
    print(f"\nModule performance — {d['module_count']} modules, "
          f"{t['enrolments']} enrolments")
    print(f"  Overall pass rate: {_pct(t['overall_pass_rate'])}   "
          f"(pass={t['pass']} fail={t['fail']} in-progress={t['in_progress']})")
    print("-" * 74)
    print(f"  {'Module':<34} {'Enrol':>5} {'Pass%':>7} {'InProg':>7}")
    for m in d["modules"]:
        name = m["module_name"] or m["module_code"]
        print(f"  {str(name)[:34]:<34} {m['enrolments']:>5} "
              f"{_pct(m['pass_rate']):>7} {m['in_progress']:>7}")


def _capacity(svc: InstitutionalAnalyticsService) -> None:
    d = svc.course_capacity()
    print(f"\nCourse capacity — {d['course_count']} courses")
    print(f"  Enrolled {d['total_enrolled']} / {d['total_capacity']} capacity "
          f"= {_pct(d['overall_fill_rate'])} filled   "
          f"({d['courses_at_capacity']} at capacity)")
    print("-" * 70)
    print(f"  {'Course':<30} {'Enrol':>6} {'Cap':>6} {'Fill%':>8}")
    for c in d["courses"]:
        name = c["course_name"] or c["course_code"]
        flag = "  FULL" if c["at_capacity"] else ""
        print(f"  {str(name)[:30]:<30} {c['enrolled']:>6} {c['capacity']:>6} "
              f"{_pct(c['fill_rate']):>8}{flag}")


def _finance(svc: InstitutionalAnalyticsService) -> None:
    d = svc.financial_summary()
    rev = d.get("revenue")
    if rev:
        print(f"\nRevenue collected: {_money(rev['collected_total'])} "
              f"across {rev['payment_count']} payments")
        if rev["by_method"]:
            print("  By method:")
            for method, amt in rev["by_method"].items():
                print(f"    {method[:26]:<26} {_money(amt):>16}")
        if rev["by_month"]:
            print("  By month:")
            for ym, amt in rev["by_month"].items():
                print(f"    {ym:<26} {_money(amt):>16}")
    fees = d.get("fees")
    if fees:
        print(f"\n  Fees outstanding: {_money(fees['outstanding_total'])}   "
              f"waived: {_money(fees['waived_total'])}")
    acct = d.get("accounts")
    if acct:
        print(f"  Finance accounts: {acct['account_count']}   "
              f"total balance: {_money(acct['total_balance'])}")


def _demographics(svc: InstitutionalAnalyticsService) -> None:
    d = svc.demographics()
    print("\nDemographics")
    print("-" * 40)
    print("  Gender:")
    for row in d["by_gender"]:
        print(f"    {row['label'][:20]:<20} {row['count']:>4}")
    for label, key in (("Age", "age"), ("UCAS tariff", "ucas_tariff"), ("GPA", "gpa")):
        s = d[key]
        if s["count"]:
            print(f"  {label}: n={s['count']} min={s['min']} "
                  f"avg={s['avg']} max={s['max']}")
        else:
            print(f"  {label}: (no data)")


# ---------------------------------------------------------------- top-level
def display_institutional_analytics_menu() -> None:
    """Top-level institutional analytics menu."""
    if not _require_login():
        return
    db_path = getattr(auth, "_db_path", None)
    svc = InstitutionalAnalyticsService(db_path)

    actions = {
        "1": ("Institutional Overview", _overview),
        "2": ("Enrolment Summary", _enrollment),
        "3": ("Retention & Attrition", _retention),
        "4": ("Module Performance", _modules),
        "5": ("Course Capacity", _capacity),
        "6": ("Financial Summary", _finance),
        "7": ("Demographics", _demographics),
    }
    while True:
        print("\nInstitutional Analytics")
        print("=" * 30)
        for k, (label, _) in actions.items():
            print(f"{k}. {label}")
        print("0. Return to Previous Menu")
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if not action:
            print("Invalid choice.")
            continue
        try:
            action[1](svc)
        except KeyboardInterrupt:
            print("\nCancelled.")
        except InstitutionalAnalyticsError as exc:
            print(f"Error: {exc}")
