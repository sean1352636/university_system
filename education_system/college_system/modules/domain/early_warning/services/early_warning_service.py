"""Early Warning System service for managing student alerts and rules."""

from education_system.college_system.core.exceptions import EarlyWarningError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class EarlyWarningService:
    """Early Warning System service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ---- Alerts ----

    def create_alert(self, student_id: int, alert_type: str, *,
                     severity: str = "medium", trigger_source: str = None,
                     trigger_detail: str = None, attendance_pct: float = None,
                     grade_trend: str = None, behaviour_count: int = None,
                     recommended_action: str = None,
                     assigned_to: int = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO early_warning_alerts
                   (student_id, alert_type, severity, trigger_source,
                    trigger_detail, attendance_pct, grade_trend,
                    behaviour_count, recommended_action, assigned_to)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, alert_type, severity, trigger_source,
                 trigger_detail, attendance_pct, grade_trend,
                 behaviour_count, recommended_action, assigned_to))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM early_warning_alerts WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise EarlyWarningError(f"Failed to create alert: {e}") from e
        finally:
            conn.close()

    def list_alerts(self, *, student_id: int = None, alert_type: str = None,
                    severity: str = None, resolved: int = None,
                    search: str = None, limit: int = 200) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT a.*, s.first_name, s.last_name
                     FROM early_warning_alerts a
                     LEFT JOIN students s ON a.student_id = s.id
                     WHERE 1=1"""
            params: list = []
            if student_id:
                sql += " AND a.student_id = ?"
                params.append(student_id)
            if alert_type:
                sql += " AND a.alert_type = ?"
                params.append(alert_type)
            if severity:
                sql += " AND a.severity = ?"
                params.append(severity)
            if resolved is not None:
                sql += " AND a.resolved = ?"
                params.append(resolved)
            if search:
                sql += (" AND (s.first_name LIKE ? OR s.last_name LIKE ?"
                        " OR a.trigger_detail LIKE ?)")
                term = f"%{search}%"
                params.extend([term, term, term])
            sql += " ORDER BY a.created_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_alert(self, alert_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT a.*, s.first_name, s.last_name
                   FROM early_warning_alerts a
                   LEFT JOIN students s ON a.student_id = s.id
                   WHERE a.id = ?""", (alert_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_alert(self, alert_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {
                "alert_type", "severity", "trigger_source", "trigger_detail",
                "attendance_pct", "grade_trend", "behaviour_count",
                "recommended_action", "assigned_to", "action_taken",
                "resolved", "resolved_at",
            }
            parts, params = ["updated_at = datetime('now')"], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 2:
                raise EarlyWarningError("No valid fields to update.")
            params.append(alert_id)
            conn.execute(
                f"UPDATE early_warning_alerts SET {', '.join(parts)} WHERE id = ?",
                params)
            conn.commit()
            return self.get_alert(alert_id)
        except EarlyWarningError:
            raise
        except Exception as e:
            conn.rollback()
            raise EarlyWarningError(f"Failed to update alert: {e}") from e
        finally:
            conn.close()

    def resolve_alert(self, alert_id: int, action_taken: str) -> dict:
        """Mark an alert as resolved."""
        return self.update_alert(
            alert_id, resolved=1, resolved_at="datetime('now')",
            action_taken=action_taken)

    def delete_alert(self, alert_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM early_warning_alerts WHERE id = ?",
                         (alert_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise EarlyWarningError(f"Failed to delete alert: {e}") from e
        finally:
            conn.close()

    # ---- Rules ----

    def create_rule(self, rule_name: str, rule_type: str, threshold: float, *,
                    comparison: str = "less_than", severity: str = "medium",
                    auto_assign_role: str = None,
                    is_active: int = 1) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO early_warning_rules
                   (rule_name, rule_type, threshold, comparison,
                    severity, auto_assign_role, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (rule_name, rule_type, threshold, comparison,
                 severity, auto_assign_role, is_active))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM early_warning_rules WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise EarlyWarningError(f"Failed to create rule: {e}") from e
        finally:
            conn.close()

    def list_rules(self, *, is_active: int = None,
                   rule_type: str = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM early_warning_rules WHERE 1=1"
            params: list = []
            if is_active is not None:
                sql += " AND is_active = ?"
                params.append(is_active)
            if rule_type:
                sql += " AND rule_type = ?"
                params.append(rule_type)
            sql += " ORDER BY rule_name"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_rule(self, rule_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM early_warning_rules WHERE id = ?", (rule_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_rule(self, rule_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"rule_name", "rule_type", "threshold", "comparison",
                        "severity", "auto_assign_role", "is_active"}
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if not parts:
                raise EarlyWarningError("No valid fields to update.")
            params.append(rule_id)
            conn.execute(
                f"UPDATE early_warning_rules SET {', '.join(parts)} WHERE id = ?",
                params)
            conn.commit()
            return self.get_rule(rule_id)
        except EarlyWarningError:
            raise
        except Exception as e:
            conn.rollback()
            raise EarlyWarningError(f"Failed to update rule: {e}") from e
        finally:
            conn.close()

    def delete_rule(self, rule_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM early_warning_rules WHERE id = ?",
                         (rule_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise EarlyWarningError(f"Failed to delete rule: {e}") from e
        finally:
            conn.close()

    # ---- Statistics ----

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM early_warning_alerts").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM early_warning_alerts WHERE resolved = 0"
            ).fetchone()[0]
            resolved = conn.execute(
                "SELECT COUNT(*) FROM early_warning_alerts WHERE resolved = 1"
            ).fetchone()[0]
            by_severity = {}
            for row in conn.execute(
                """SELECT severity, COUNT(*) as cnt FROM early_warning_alerts
                   WHERE resolved = 0 GROUP BY severity"""
            ).fetchall():
                by_severity[row["severity"]] = row["cnt"]
            by_type = {}
            for row in conn.execute(
                """SELECT alert_type, COUNT(*) as cnt FROM early_warning_alerts
                   WHERE resolved = 0 GROUP BY alert_type"""
            ).fetchall():
                by_type[row["alert_type"]] = row["cnt"]
            rules = conn.execute(
                "SELECT COUNT(*) FROM early_warning_rules WHERE is_active = 1"
            ).fetchone()[0]
            return {
                "total_alerts": total, "active_alerts": active,
                "resolved_alerts": resolved, "active_rules": rules,
                "active_by_severity": by_severity,
                "active_by_type": by_type,
            }
        finally:
            conn.close()
