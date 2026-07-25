"""Institutional KPI dashboard service.

Reads from the existing analytics_bi schema (kpi_metrics, analytics_dashboards,
dashboard_widgets). No DDL is performed here.

Schema reference (analytics_bi_schemas.py):
- kpi_metrics(kpi_id, kpi_name, kpi_category, current_value, target_value,
              measurement_date, period, trend, created_at)
- analytics_dashboards(dashboard_id, dashboard_name, dashboard_type, owner_id,
                       is_public, layout_config, widget_config,
                       created_at, updated_at)
- dashboard_widgets(widget_id, dashboard_id, widget_type, widget_title,
                    data_source, chart_type, position_x, position_y,
                    width, height, config)

Note: `kpi_metrics` has no owner column (the brief asked for owner-filtering on
KPIs, but only `kpi_category` is available). The owner concept lives on the
dashboard side (`analytics_dashboards.owner_id`), so list_dashboards supports
owner-filtering instead.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import Any, Optional

from education_system.systems.university.infrastructure.database.db import get_connection


class KpiDashboardError(Exception):
    """Raised on validation / lookup failures within the KPI dashboard service."""


# Status thresholds (fraction of target). Defaults: >=0.95 on-target,
# >=0.80 at-risk, otherwise off-target. "Higher is better" semantics.
DEFAULT_ON_TARGET = 0.95
DEFAULT_AT_RISK = 0.80


class KpiDashboardService:
    """Read-mostly service exposing KPIs and dashboards built on top of them."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path

    # ----------------------------------------------------------------- helpers
    def _conn(self) -> sqlite3.Connection:
        return get_connection(self.db_path) if self.db_path else get_connection()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> Optional[dict[str, Any]]:
        return dict(row) if row is not None else None

    @staticmethod
    def _safe_json(text: Any) -> Any:
        if not text:
            return None
        if isinstance(text, (dict, list)):
            return text
        try:
            return json.loads(text)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_kpi_ref(widget: dict[str, Any]) -> Optional[int]:
        """Pull a kpi_id reference out of a widget's config or data_source."""
        for field in ("config", "data_source"):
            parsed = KpiDashboardService._safe_json(widget.get(field))
            if isinstance(parsed, dict) and parsed.get("kpi_id") is not None:
                try:
                    return int(parsed["kpi_id"])
                except (TypeError, ValueError):
                    continue
        # Plain string fallback: data_source like "kpi:42"
        ds = widget.get("data_source")
        if isinstance(ds, str) and ds.lower().startswith("kpi:"):
            try:
                return int(ds.split(":", 1)[1])
            except ValueError:
                return None
        return None

    # ------------------------------------------------------------------ KPIs
    def list_kpis(
        self,
        category: Optional[str] = None,
        owner: Optional[str] = None,  # accepted but unused — see module docstring
    ) -> list[dict[str, Any]]:
        """List KPIs, optionally filtered by category.

        `owner` is accepted for API completeness but is not honoured because
        the kpi_metrics table has no owner column.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if category:
            clauses.append("kpi_category = ?")
            params.append(category)
        sql = "SELECT * FROM kpi_metrics"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY kpi_category, kpi_name"
        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        result = [dict(r) for r in rows]
        if owner:
            # Surface in each row so callers can see filter was a no-op.
            for r in result:
                r["_owner_filter_ignored"] = owner
        return result

    def get_kpi(self, kpi_id: int) -> dict[str, Any]:
        if not isinstance(kpi_id, int) or kpi_id <= 0:
            raise KpiDashboardError("kpi_id must be a positive integer")
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM kpi_metrics WHERE kpi_id = ?", (kpi_id,)
            ).fetchone()
        finally:
            conn.close()
        kpi = self._row_to_dict(row)
        if kpi is None:
            raise KpiDashboardError(f"KPI {kpi_id} not found")
        return kpi

    def update_kpi_actual(
        self,
        kpi_id: int,
        value: float,
        as_of_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update current_value and measurement_date for a KPI."""
        if not isinstance(kpi_id, int) or kpi_id <= 0:
            raise KpiDashboardError("kpi_id must be a positive integer")
        try:
            value = float(value)
        except (TypeError, ValueError) as exc:
            raise KpiDashboardError("value must be numeric") from exc
        if as_of_date is None:
            as_of_date = date.today().isoformat()
        else:
            try:
                datetime.strptime(as_of_date, "%Y-%m-%d")
            except ValueError as exc:
                raise KpiDashboardError(
                    "as_of_date must be ISO YYYY-MM-DD"
                ) from exc
        conn = self._conn()
        try:
            cur = conn.execute(
                "UPDATE kpi_metrics SET current_value = ?, measurement_date = ? "
                "WHERE kpi_id = ?",
                (value, as_of_date, kpi_id),
            )
            if cur.rowcount == 0:
                raise KpiDashboardError(f"KPI {kpi_id} not found")
            conn.commit()
        finally:
            conn.close()
        return self.get_kpi(kpi_id)

    def kpi_status(
        self,
        kpi: int | dict[str, Any],
        on_target_threshold: float = DEFAULT_ON_TARGET,
        at_risk_threshold: float = DEFAULT_AT_RISK,
    ) -> dict[str, Any]:
        """Compute on_target / at_risk / off_target plus gap and progress %.

        `kpi` may be either a kpi_id or an already-loaded KPI dict.
        Thresholds are fractions of the target (higher-is-better semantics).
        """
        if not (0 < at_risk_threshold <= on_target_threshold <= 2.0):
            raise KpiDashboardError(
                "thresholds must satisfy 0 < at_risk <= on_target <= 2.0"
            )
        data = self.get_kpi(kpi) if isinstance(kpi, int) else dict(kpi)
        current = data.get("current_value")
        target = data.get("target_value")
        if current is None:
            raise KpiDashboardError("KPI is missing current_value")
        if target is None or target == 0:
            return {
                "kpi_id": data.get("kpi_id"),
                "kpi_name": data.get("kpi_name"),
                "current_value": current,
                "target_value": target,
                "progress_pct": None,
                "gap_to_target": None,
                "status": "no_target",
            }
        ratio = float(current) / float(target)
        if ratio >= on_target_threshold:
            status = "on_target"
        elif ratio >= at_risk_threshold:
            status = "at_risk"
        else:
            status = "off_target"
        return {
            "kpi_id": data.get("kpi_id"),
            "kpi_name": data.get("kpi_name"),
            "current_value": float(current),
            "target_value": float(target),
            "progress_pct": round(ratio * 100, 2),
            "gap_to_target": round(float(target) - float(current), 4),
            "status": status,
        }

    # ------------------------------------------------------------ Dashboards
    def list_dashboards(
        self,
        owner_id: Optional[str] = None,
        public_only: bool = False,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if owner_id:
            clauses.append("owner_id = ?")
            params.append(owner_id)
        if public_only:
            clauses.append("is_public = 1")
        sql = "SELECT * FROM analytics_dashboards"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY dashboard_name"
        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def get_dashboard(self, dashboard_id: int) -> dict[str, Any]:
        """Return dashboard meta + ordered widgets, each with resolved KPI snapshot."""
        if not isinstance(dashboard_id, int) or dashboard_id <= 0:
            raise KpiDashboardError("dashboard_id must be a positive integer")
        conn = self._conn()
        try:
            dash_row = conn.execute(
                "SELECT * FROM analytics_dashboards WHERE dashboard_id = ?",
                (dashboard_id,),
            ).fetchone()
            if dash_row is None:
                raise KpiDashboardError(f"Dashboard {dashboard_id} not found")
            widget_rows = conn.execute(
                "SELECT * FROM dashboard_widgets WHERE dashboard_id = ? "
                "ORDER BY position_y, position_x, widget_id",
                (dashboard_id,),
            ).fetchall()
            widgets: list[dict[str, Any]] = []
            for wrow in widget_rows:
                w = dict(wrow)
                kpi_id = self._extract_kpi_ref(w)
                kpi_snapshot: Optional[dict[str, Any]] = None
                status: Optional[dict[str, Any]] = None
                if kpi_id is not None:
                    krow = conn.execute(
                        "SELECT * FROM kpi_metrics WHERE kpi_id = ?", (kpi_id,)
                    ).fetchone()
                    if krow is not None:
                        kpi_snapshot = dict(krow)
                        try:
                            status = self.kpi_status(kpi_snapshot)
                        except KpiDashboardError:
                            status = None
                w["resolved_kpi_id"] = kpi_id
                w["kpi"] = kpi_snapshot
                w["status"] = status
                widgets.append(w)
        finally:
            conn.close()
        return {
            "dashboard": dict(dash_row),
            "widgets": widgets,
            "widget_count": len(widgets),
        }
