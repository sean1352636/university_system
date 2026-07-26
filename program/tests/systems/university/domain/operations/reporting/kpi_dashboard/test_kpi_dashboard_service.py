"""Tests for the institutional KPI dashboard service.

The service is read-mostly over kpi_metrics / analytics_dashboards /
dashboard_widgets. Each test seeds a fresh SQLite file with the
analytics_bi schema and exercises the service against it.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from education_system.systems.university.infrastructure.database import db as db_module
from education_system.systems.university.domain.operations.reporting.kpi_dashboard.services.kpi_dashboard_service import (
    DEFAULT_AT_RISK,
    DEFAULT_ON_TARGET,
    KpiDashboardError,
    KpiDashboardService,
)


KPI_SCHEMA = """
CREATE TABLE kpi_metrics (
    kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
    kpi_name TEXT NOT NULL,
    kpi_category TEXT NOT NULL,
    current_value REAL NOT NULL,
    target_value REAL,
    measurement_date TEXT DEFAULT CURRENT_DATE,
    period TEXT,
    trend TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE analytics_dashboards (
    dashboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dashboard_name TEXT NOT NULL,
    dashboard_type TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    is_public INTEGER DEFAULT 0,
    layout_config TEXT,
    widget_config TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE dashboard_widgets (
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
);
"""


@pytest.fixture
def kpi_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "kpi_test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    conn = sqlite3.connect(db_path)
    conn.executescript(KPI_SCHEMA)
    conn.commit()
    conn.close()
    yield db_path


def _seed_kpi(name="Graduate Employability", category="academic",
              current=90.0, target=100.0) -> int:
    from education_system.systems.university.infrastructure.database.db import get_connection
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO kpi_metrics (kpi_name, kpi_category, current_value, target_value) "
            "VALUES (?, ?, ?, ?)", (name, category, current, target),
        )
        conn.commit()
        return cur.lastrowid


def _seed_dashboard(name="Exec Overview", dtype="institutional",
                    owner="provost", is_public=False) -> int:
    from education_system.systems.university.infrastructure.database.db import get_connection
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO analytics_dashboards "
            "(dashboard_name, dashboard_type, owner_id, is_public) VALUES (?, ?, ?, ?)",
            (name, dtype, owner, 1 if is_public else 0),
        )
        conn.commit()
        return cur.lastrowid


def _seed_widget(dashboard_id: int, kpi_id: int | None = None,
                 data_source: str | None = None, config: str | None = None,
                 position=(0, 0), title="KPI Tile") -> int:
    from education_system.systems.university.infrastructure.database.db import get_connection
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO dashboard_widgets "
            "(dashboard_id, widget_type, widget_title, data_source, chart_type, "
            " position_x, position_y, config) VALUES (?, 'kpi', ?, ?, 'number', ?, ?, ?)",
            (dashboard_id, title, data_source, position[0], position[1], config),
        )
        conn.commit()
        return cur.lastrowid


class TestListKpis:
    def test_returns_empty_when_no_kpis(self, kpi_db):
        svc = KpiDashboardService()
        assert svc.list_kpis() == []

    def test_filter_by_category(self, kpi_db):
        _seed_kpi("Retention", "academic", 92, 95)
        _seed_kpi("Surplus", "financial", 1000, 2000)
        svc = KpiDashboardService()
        rows = svc.list_kpis(category="financial")
        assert len(rows) == 1
        assert rows[0]["kpi_name"] == "Surplus"

    def test_owner_filter_is_noop_but_annotated(self, kpi_db):
        _seed_kpi()
        svc = KpiDashboardService()
        rows = svc.list_kpis(owner="provost")
        assert len(rows) == 1
        assert rows[0]["_owner_filter_ignored"] == "provost"

    def test_ordered_by_category_then_name(self, kpi_db):
        _seed_kpi("Zeta", "academic", 1, 2)
        _seed_kpi("Alpha", "academic", 1, 2)
        _seed_kpi("Beta", "financial", 1, 2)
        svc = KpiDashboardService()
        names = [r["kpi_name"] for r in svc.list_kpis()]
        assert names == ["Alpha", "Zeta", "Beta"]


class TestGetKpi:
    def test_rejects_non_positive_id(self, kpi_db):
        svc = KpiDashboardService()
        with pytest.raises(KpiDashboardError, match="positive integer"):
            svc.get_kpi(0)
        with pytest.raises(KpiDashboardError, match="positive integer"):
            svc.get_kpi(-1)

    def test_missing_kpi_raises(self, kpi_db):
        svc = KpiDashboardService()
        with pytest.raises(KpiDashboardError, match="not found"):
            svc.get_kpi(12345)

    def test_returns_row_dict(self, kpi_db):
        kid = _seed_kpi("Retention", "academic", 92, 95)
        svc = KpiDashboardService()
        kpi = svc.get_kpi(kid)
        assert kpi["kpi_name"] == "Retention"
        assert kpi["target_value"] == 95


class TestUpdateKpiActual:
    def test_updates_value_and_returns_refreshed_row(self, kpi_db):
        kid = _seed_kpi(current=10.0, target=100.0)
        svc = KpiDashboardService()
        updated = svc.update_kpi_actual(kid, 42.5, as_of_date="2026-05-01")
        assert updated["current_value"] == pytest.approx(42.5)
        assert updated["measurement_date"] == "2026-05-01"

    def test_defaults_as_of_date_to_today(self, kpi_db):
        kid = _seed_kpi()
        svc = KpiDashboardService()
        updated = svc.update_kpi_actual(kid, 50.0)
        assert updated["measurement_date"]  # populated to today's ISO date

    def test_rejects_bad_date_format(self, kpi_db):
        kid = _seed_kpi()
        svc = KpiDashboardService()
        with pytest.raises(KpiDashboardError, match="ISO YYYY-MM-DD"):
            svc.update_kpi_actual(kid, 1.0, as_of_date="01/05/2026")

    def test_rejects_non_numeric_value(self, kpi_db):
        kid = _seed_kpi()
        svc = KpiDashboardService()
        with pytest.raises(KpiDashboardError, match="numeric"):
            svc.update_kpi_actual(kid, "not-a-number")

    def test_missing_kpi_raises(self, kpi_db):
        svc = KpiDashboardService()
        with pytest.raises(KpiDashboardError, match="not found"):
            svc.update_kpi_actual(999, 10.0)


class TestKpiStatus:
    def test_on_target(self, kpi_db):
        kid = _seed_kpi(current=98, target=100)
        svc = KpiDashboardService()
        status = svc.kpi_status(kid)
        assert status["status"] == "on_target"
        assert status["progress_pct"] == 98.0
        assert status["gap_to_target"] == pytest.approx(2.0)

    def test_at_risk(self, kpi_db):
        kid = _seed_kpi(current=85, target=100)
        svc = KpiDashboardService()
        assert svc.kpi_status(kid)["status"] == "at_risk"

    def test_off_target(self, kpi_db):
        kid = _seed_kpi(current=50, target=100)
        svc = KpiDashboardService()
        assert svc.kpi_status(kid)["status"] == "off_target"

    def test_no_target_when_target_missing_or_zero(self, kpi_db):
        kid = _seed_kpi(current=10, target=0)
        svc = KpiDashboardService()
        out = svc.kpi_status(kid)
        assert out["status"] == "no_target"
        assert out["progress_pct"] is None
        assert out["gap_to_target"] is None

    def test_accepts_dict_directly(self, kpi_db):
        svc = KpiDashboardService()
        out = svc.kpi_status(
            {"kpi_id": 1, "kpi_name": "x", "current_value": 50, "target_value": 50},
        )
        assert out["status"] == "on_target"

    def test_invalid_thresholds_raise(self, kpi_db):
        kid = _seed_kpi()
        svc = KpiDashboardService()
        with pytest.raises(KpiDashboardError, match="thresholds"):
            svc.kpi_status(kid, on_target_threshold=0.5, at_risk_threshold=0.8)

    def test_default_thresholds_are_consistent(self):
        assert DEFAULT_AT_RISK < DEFAULT_ON_TARGET <= 2.0


class TestDashboards:
    def test_list_filters_by_owner_and_public(self, kpi_db):
        _seed_dashboard("A", owner="provost", is_public=False)
        _seed_dashboard("B", owner="provost", is_public=True)
        _seed_dashboard("C", owner="dean", is_public=True)
        svc = KpiDashboardService()
        assert {d["dashboard_name"] for d in svc.list_dashboards(owner_id="provost")} == {"A", "B"}
        assert {d["dashboard_name"] for d in svc.list_dashboards(public_only=True)} == {"B", "C"}
        assert {d["dashboard_name"] for d in
                svc.list_dashboards(owner_id="provost", public_only=True)} == {"B"}

    def test_get_dashboard_rejects_bad_id(self, kpi_db):
        svc = KpiDashboardService()
        with pytest.raises(KpiDashboardError, match="positive integer"):
            svc.get_dashboard(0)

    def test_get_dashboard_missing_raises(self, kpi_db):
        svc = KpiDashboardService()
        with pytest.raises(KpiDashboardError, match="not found"):
            svc.get_dashboard(999)

    def test_get_dashboard_resolves_kpi_via_config_json(self, kpi_db):
        kid = _seed_kpi(current=90, target=100)
        did = _seed_dashboard()
        _seed_widget(did, config=json.dumps({"kpi_id": kid}))
        svc = KpiDashboardService()
        result = svc.get_dashboard(did)
        assert result["widget_count"] == 1
        w = result["widgets"][0]
        assert w["resolved_kpi_id"] == kid
        assert w["kpi"]["kpi_id"] == kid
        assert w["status"]["status"] == "at_risk"

    def test_get_dashboard_resolves_kpi_via_data_source_prefix(self, kpi_db):
        kid = _seed_kpi(current=100, target=100)
        did = _seed_dashboard()
        _seed_widget(did, data_source=f"kpi:{kid}")
        svc = KpiDashboardService()
        result = svc.get_dashboard(did)
        w = result["widgets"][0]
        assert w["resolved_kpi_id"] == kid
        assert w["status"]["status"] == "on_target"

    def test_get_dashboard_widget_without_kpi_ref(self, kpi_db):
        did = _seed_dashboard()
        _seed_widget(did, data_source="random:not-a-kpi")
        svc = KpiDashboardService()
        result = svc.get_dashboard(did)
        w = result["widgets"][0]
        assert w["resolved_kpi_id"] is None
        assert w["kpi"] is None
        assert w["status"] is None

    def test_get_dashboard_orders_widgets_by_position(self, kpi_db):
        did = _seed_dashboard()
        _seed_widget(did, data_source="kpi:0", position=(0, 2), title="bottom")
        _seed_widget(did, data_source="kpi:0", position=(0, 0), title="top")
        _seed_widget(did, data_source="kpi:0", position=(0, 1), title="middle")
        svc = KpiDashboardService()
        titles = [w["widget_title"] for w in svc.get_dashboard(did)["widgets"]]
        assert titles == ["top", "middle", "bottom"]

    def test_get_dashboard_dangling_kpi_ref_leaves_status_none(self, kpi_db):
        did = _seed_dashboard()
        _seed_widget(did, data_source="kpi:9999")
        svc = KpiDashboardService()
        w = svc.get_dashboard(did)["widgets"][0]
        assert w["resolved_kpi_id"] == 9999
        assert w["kpi"] is None
        assert w["status"] is None
