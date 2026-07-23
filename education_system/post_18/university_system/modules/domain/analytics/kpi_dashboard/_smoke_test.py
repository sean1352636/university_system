"""Standalone smoke test for KpiDashboardService against an isolated temp DB.

Not part of the pytest suite — run directly:
    python -m \
      education_system.post_18.university_system.modules.domain.analytics.kpi_dashboard._smoke_test
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

# Put the repo root (the directory containing the top-level education_system
# package) on sys.path so this file runs without an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parents[7]))

from education_system.post_18.university_system.modules.domain.analytics.kpi_dashboard.services.kpi_dashboard_service import (  # noqa: E402
    KpiDashboardError,
    KpiDashboardService,
)


def build_db(path: str) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS kpi_metrics (
            kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
            kpi_name TEXT NOT NULL,
            kpi_category TEXT NOT NULL,
            current_value REAL NOT NULL,
            target_value REAL,
            measurement_date TEXT DEFAULT CURRENT_DATE,
            period TEXT,
            trend TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS analytics_dashboards (
            dashboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dashboard_name TEXT NOT NULL,
            dashboard_type TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            is_public BOOLEAN DEFAULT 0,
            layout_config TEXT,
            widget_config TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS dashboard_widgets (
            widget_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dashboard_id INTEGER NOT NULL,
            widget_type TEXT NOT NULL,
            widget_title TEXT NOT NULL,
            data_source TEXT,
            chart_type TEXT,
            position_x INTEGER,
            position_y INTEGER,
            width INTEGER DEFAULT 4,
            height INTEGER DEFAULT 3,
            config TEXT
        )
    ''')

    cur.executemany(
        "INSERT INTO kpi_metrics(kpi_name, kpi_category, current_value, target_value, "
        "period, trend) VALUES (?,?,?,?,?,?)",
        [
            ("Student retention rate", "academic", 92.0, 95.0, "annual", "stable"),
            ("Graduate employment rate", "outcomes", 78.0, 90.0, "annual", "down"),
            ("Module pass rate", "academic", 88.0, 85.0, "semester", "up"),
        ],
    )
    cur.execute(
        "INSERT INTO analytics_dashboards(dashboard_name, dashboard_type, owner_id, is_public)"
        " VALUES (?,?,?,?)",
        ("Executive KPI overview", "executive", "vp_academic", 1),
    )
    dash_id = cur.lastrowid
    cur.executemany(
        "INSERT INTO dashboard_widgets(dashboard_id, widget_type, widget_title, data_source,"
        " chart_type, position_x, position_y, config) VALUES (?,?,?,?,?,?,?,?)",
        [
            (dash_id, "kpi_card", "Retention", "kpi:1", "gauge", 0, 0, None),
            (dash_id, "kpi_card", "Employment", None, "gauge", 1, 0,
             json.dumps({"kpi_id": 2})),
            (dash_id, "kpi_card", "Pass rate", None, "gauge", 0, 1,
             json.dumps({"kpi_id": 3})),
            (dash_id, "note", "Notes panel", "static:notes", "text", 1, 1, None),
        ],
    )
    conn.commit()
    conn.close()


def main() -> int:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    path = tmp.name
    try:
        build_db(path)
        svc = KpiDashboardService(path)

        print("== list_kpis (all) ==")
        all_kpis = svc.list_kpis()
        for k in all_kpis:
            print(f"  #{k['kpi_id']} {k['kpi_name']:<28} cat={k['kpi_category']:<10} "
                  f"cur={k['current_value']} tgt={k['target_value']}")
        assert len(all_kpis) == 3

        print("\n== list_kpis (category=academic) ==")
        ac = svc.list_kpis(category="academic")
        for k in ac:
            print(f"  #{k['kpi_id']} {k['kpi_name']}")
        assert len(ac) == 2

        print("\n== kpi_status for each ==")
        statuses: dict[int, str] = {}
        for k in all_kpis:
            st = svc.kpi_status(k)
            statuses[st['kpi_id']] = st['status']
            print(f"  #{st['kpi_id']:>2} {st['kpi_name']:<28} "
                  f"status={st['status']:<11} progress={st['progress_pct']}% "
                  f"gap={st['gap_to_target']}")
        # 92/95=0.968 on_target, 78/90=0.866 at_risk, 88/85=1.035 on_target
        assert statuses[1] == "on_target", statuses
        assert statuses[2] == "at_risk", statuses
        assert statuses[3] == "on_target", statuses

        print("\n== update_kpi_actual(2, 60.0, '2026-04-25') ==")
        updated = svc.update_kpi_actual(2, 60.0, as_of_date="2026-04-25")
        print(f"  new current={updated['current_value']} measured={updated['measurement_date']}")
        st2 = svc.kpi_status(2)
        print(f"  recomputed status={st2['status']} progress={st2['progress_pct']}%")
        # 60/90 = 0.667 -> off_target
        assert st2["status"] == "off_target"

        print("\n== list_dashboards ==")
        dlist = svc.list_dashboards()
        for d in dlist:
            print(f"  #{d['dashboard_id']} {d['dashboard_name']} owner={d['owner_id']}")
        assert len(dlist) == 1

        print("\n== get_dashboard(1) ==")
        dash = svc.get_dashboard(1)
        print(f"  dashboard: {dash['dashboard']['dashboard_name']} "
              f"({dash['widget_count']} widgets)")
        for w in dash["widgets"]:
            kpi = w.get("kpi")
            st = w.get("status")
            print(f"   widget {w['widget_id']:>2} {w['widget_title']:<14} "
                  f"resolved_kpi={w['resolved_kpi_id']} "
                  f"{'kpi='+str(kpi['kpi_name']) if kpi else 'kpi=None'} "
                  f"status={(st or {}).get('status') if st else '-'}")
        assert dash["widget_count"] == 4
        resolved = [w for w in dash["widgets"] if w["resolved_kpi_id"] is not None]
        assert len(resolved) == 3

        print("\n== validation: get_kpi(999) should error ==")
        try:
            svc.get_kpi(999)
        except KpiDashboardError as exc:
            print(f"  OK -> {exc}")

        print("\nAll smoke assertions passed.")
        return 0
    finally:
        os.unlink(path)


if __name__ == "__main__":
    raise SystemExit(main())
