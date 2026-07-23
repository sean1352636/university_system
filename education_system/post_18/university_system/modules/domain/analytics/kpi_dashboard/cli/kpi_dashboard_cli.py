"""Console menu for the institutional KPI dashboard.

Style mirrors employer_portal_cli.py: function-based dispatch, simple
prompt/print interactions, single shared service instance per session.
"""
from __future__ import annotations

from typing import Any

from education_system.post_18.university_system.modules.domain.analytics.kpi_dashboard.services.kpi_dashboard_service import (
    KpiDashboardError,
    KpiDashboardService,
)


auth: Any = None


def set_auth(auth_object: Any) -> None:
    global auth
    auth = auth_object


def _require_login() -> bool:
    if not auth or not getattr(auth, "current_user", None):
        print("You must be logged in to access the KPI dashboard.")
        return False
    return True


# ---------------------------------------------------------------- formatting
def _fmt_num(v: Any, width: int = 10) -> str:
    if v is None:
        return f"{'-':>{width}}"
    try:
        return f"{float(v):>{width}.2f}"
    except (TypeError, ValueError):
        return f"{str(v):>{width}}"


def _status_label(s: dict[str, Any] | None) -> str:
    if not s:
        return "-"
    return s.get("status") or "-"


# --------------------------------------------------------------- KPI actions
def _list_kpis(svc: KpiDashboardService) -> None:
    cat = input("Filter by category (Enter for all): ").strip() or None
    try:
        kpis = svc.list_kpis(category=cat)
    except KpiDashboardError as exc:
        print(f"Error: {exc}")
        return
    if not kpis:
        print("No KPIs found.")
        return
    print(f"\n{'ID':<5} {'Name':<30} {'Category':<18} "
          f"{'Current':>10} {'Target':>10} {'Status':<11} {'Progress':>9}")
    print("-" * 96)
    for k in kpis:
        try:
            st = svc.kpi_status(k)
        except KpiDashboardError:
            st = None
        prog = "-" if not st or st.get("progress_pct") is None else f"{st['progress_pct']:.1f}%"
        print(f"{k['kpi_id']:<5} "
              f"{(k.get('kpi_name') or '')[:30]:<30} "
              f"{(k.get('kpi_category') or '-')[:18]:<18} "
              f"{_fmt_num(k.get('current_value'))} "
              f"{_fmt_num(k.get('target_value'))} "
              f"{_status_label(st):<11} "
              f"{prog:>9}")
    print(f"\nTotal: {len(kpis)}")


def _view_kpi(svc: KpiDashboardService) -> None:
    try:
        kid = int(input("KPI ID: ").strip())
        kpi = svc.get_kpi(kid)
        st = svc.kpi_status(kpi)
    except (KpiDashboardError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    print(f"\nKPI #{kpi['kpi_id']} — {kpi.get('kpi_name')}")
    print("-" * 50)
    print(f"  Category:        {kpi.get('kpi_category') or '-'}")
    print(f"  Period:          {kpi.get('period') or '-'}")
    print(f"  Trend:           {kpi.get('trend') or '-'}")
    print(f"  Current value:   {kpi.get('current_value')}")
    print(f"  Target value:    {kpi.get('target_value')}")
    print(f"  Measured on:     {kpi.get('measurement_date') or '-'}")
    print(f"  Status:          {st.get('status')}")
    print(f"  Progress:        "
          f"{st['progress_pct']}%" if st.get('progress_pct') is not None else "  Progress:        -")
    print(f"  Gap to target:   {st.get('gap_to_target')}")


def _update_actual(svc: KpiDashboardService) -> None:
    try:
        kid = int(input("KPI ID: ").strip())
        val = float(input("New current value: ").strip())
        d = input("As-of date YYYY-MM-DD (Enter for today): ").strip() or None
        kpi = svc.update_kpi_actual(kid, val, as_of_date=d)
    except (KpiDashboardError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    print(f"Updated. {kpi['kpi_name']} now {kpi['current_value']} "
          f"(measured {kpi['measurement_date']}).")


# -------------------------------------------------------- Dashboard actions
def _list_dashboards(svc: KpiDashboardService) -> None:
    owner = input("Filter by owner_id (Enter for all): ").strip() or None
    pub = input("Public only? (y/n, default=n): ").strip().lower() == "y"
    try:
        rows = svc.list_dashboards(owner_id=owner, public_only=pub)
    except KpiDashboardError as exc:
        print(f"Error: {exc}")
        return
    if not rows:
        print("No dashboards found.")
        return
    print(f"\n{'ID':<5} {'Name':<28} {'Type':<14} {'Owner':<14} {'Public':<7} {'Updated':<20}")
    print("-" * 90)
    for d in rows:
        print(f"{d['dashboard_id']:<5} "
              f"{(d.get('dashboard_name') or '')[:28]:<28} "
              f"{(d.get('dashboard_type') or '-')[:14]:<14} "
              f"{(d.get('owner_id') or '-')[:14]:<14} "
              f"{'Yes' if d.get('is_public') else 'No':<7} "
              f"{(d.get('updated_at') or '-')[:19]:<20}")
    print(f"\nTotal: {len(rows)}")


def _view_dashboard(svc: KpiDashboardService) -> None:
    try:
        did = int(input("Dashboard ID: ").strip())
        data = svc.get_dashboard(did)
    except (KpiDashboardError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    d = data["dashboard"]
    print(f"\nDashboard #{d['dashboard_id']} — {d.get('dashboard_name')}")
    print(f"Type: {d.get('dashboard_type') or '-'}    "
          f"Owner: {d.get('owner_id') or '-'}    "
          f"Public: {'Yes' if d.get('is_public') else 'No'}")
    print(f"Widgets: {data['widget_count']}")
    print("=" * 70)
    if not data["widgets"]:
        print("(no widgets configured)")
        return
    for w in data["widgets"]:
        print()
        print(f"  [{w['widget_id']}] {w.get('widget_title') or '(untitled)'}  "
              f"<{w.get('widget_type') or '-'}/{w.get('chart_type') or '-'}>")
        print(f"      pos=({w.get('position_x')},{w.get('position_y')})  "
              f"size={w.get('width')}x{w.get('height')}")
        kpi = w.get("kpi")
        st = w.get("status")
        if kpi is None:
            print(f"      data_source: {w.get('data_source') or '-'} "
                  f"(no resolved KPI)")
            continue
        print(f"      KPI #{kpi['kpi_id']} — {kpi.get('kpi_name')} "
              f"[{kpi.get('kpi_category') or '-'}]")
        print(f"      current={kpi.get('current_value')}  "
              f"target={kpi.get('target_value')}  "
              f"as_of={kpi.get('measurement_date') or '-'}")
        if st:
            prog = (f"{st['progress_pct']}%"
                    if st.get('progress_pct') is not None else "-")
            print(f"      status={st.get('status')}  "
                  f"progress={prog}  gap={st.get('gap_to_target')}")


# ---------------------------------------------------------------- top-level
def display_kpi_dashboard_menu() -> None:
    """Top-level institutional KPI dashboard menu."""
    if not _require_login():
        return
    db_path = getattr(auth, "_db_path", None)
    svc = KpiDashboardService(db_path)

    actions = {
        "1": ("List KPIs",        _list_kpis),
        "2": ("View KPI Detail",  _view_kpi),
        "3": ("Update KPI Actual", _update_actual),
        "4": ("List Dashboards",  _list_dashboards),
        "5": ("View Dashboard",   _view_dashboard),
    }
    while True:
        print("\nInstitutional KPI Dashboard")
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
        except KpiDashboardError as exc:
            print(f"Error: {exc}")
