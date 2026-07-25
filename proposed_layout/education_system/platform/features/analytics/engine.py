"""Unified analytics engine for all education systems.

Improvement #16: Dashboard Analytics

Cross-system dashboards with attendance trends, grade distributions,
at-risk student identification, and enrolment statistics.
"""

import logging
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """Cross-system analytics engine.

    Usage:
        engine = AnalyticsEngine(db_path="/path/to/system.db", system_key="sixth_form")
        stats = engine.attendance_summary(year_group="12")
        at_risk = engine.at_risk_students(threshold_attendance=85.0)
    """

    def __init__(self, db_path: str, system_key: str = "sixth_form"):
        self.db_path = db_path
        self.system_key = system_key

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def attendance_summary(self, *, year_group: str | None = None,
                           since: str | None = None, until: str | None = None) -> dict:
        """Calculate attendance summary statistics."""
        conn = self._connect()
        try:
            conditions, params = [], []
            if year_group:
                conditions.append("student_id IN (SELECT student_id FROM students WHERE year_group = ?)")
                params.append(year_group)
            if since:
                conditions.append("date >= ?")
                params.append(since)
            if until:
                conditions.append("date <= ?")
                params.append(until)

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            rows = conn.execute(
                f"SELECT status, COUNT(*) as cnt FROM attendance {where} GROUP BY status", params
            ).fetchall()

            by_status = {r["status"]: r["cnt"] for r in rows}
            total = sum(by_status.values())
            present = by_status.get("present", 0) + by_status.get("Present", 0)
            late = by_status.get("late", 0) + by_status.get("Late", 0)
            absent = total - present - late
            rate = ((present + late) / total * 100) if total > 0 else 0.0

            by_year = {}
            try:
                yg_rows = conn.execute("""
                    SELECT s.year_group, COUNT(*) as total,
                           SUM(CASE WHEN a.status IN ('present','Present','late','Late') THEN 1 ELSE 0 END) as attended
                    FROM attendance a JOIN students s ON a.student_id = s.student_id
                    GROUP BY s.year_group
                """).fetchall()
                for r in yg_rows:
                    by_year[r["year_group"]] = round(r["attended"] / r["total"] * 100, 1) if r["total"] else 0
            except sqlite3.OperationalError:
                pass

            return {"total_records": total, "present": present, "absent": absent,
                    "late": late, "attendance_rate": round(rate, 1),
                    "by_status": by_status, "by_year_group": by_year}
        finally:
            conn.close()

    def grade_distribution(self, *, course_code: str | None = None) -> dict:
        """Get grade distribution across courses."""
        conn = self._connect()
        try:
            conditions, params = [], []
            if course_code:
                conditions.append("course_code = ?")
                params.append(course_code)
            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            rows = conn.execute(
                f"SELECT grade, COUNT(*) as cnt FROM grades {where} GROUP BY grade", params
            ).fetchall()
            distribution = {r["grade"]: r["cnt"] for r in rows}
            return {"total_grades": sum(distribution.values()), "distribution": distribution}
        finally:
            conn.close()

    def at_risk_students(self, *, threshold_attendance: float = 85.0, days: int = 30) -> list[dict]:
        """Identify students at risk based on attendance below threshold."""
        conn = self._connect()
        try:
            since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            rows = conn.execute("""
                SELECT s.student_id, s.first_name, s.last_name, s.year_group, s.form_group,
                       COUNT(a.id) as total_marks,
                       SUM(CASE WHEN a.status IN ('present','Present','late','Late') THEN 1 ELSE 0 END) as attended
                FROM students s
                LEFT JOIN attendance a ON s.student_id = a.student_id AND a.date >= ?
                WHERE s.status = 'active' OR s.status IS NULL
                GROUP BY s.student_id HAVING total_marks > 0
                ORDER BY (CAST(attended AS FLOAT) / total_marks) ASC
            """, (since,)).fetchall()

            at_risk = []
            for r in rows:
                rate = (r["attended"] / r["total_marks"] * 100) if r["total_marks"] else 0
                if rate < threshold_attendance:
                    at_risk.append({
                        "student_id": r["student_id"], "first_name": r["first_name"],
                        "last_name": r["last_name"], "year_group": r["year_group"],
                        "attendance_rate": round(rate, 1),
                        "risk_level": "high" if rate < 70 else "medium" if rate < 80 else "low",
                    })
            return at_risk
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    def system_overview(self) -> dict:
        """Get a high-level overview of the system."""
        conn = self._connect()
        try:
            overview = {"system_key": self.system_key, "generated_at": datetime.now().isoformat()}
            for table, key in [("students", "total_students"), ("courses", "total_courses"),
                               ("enrollments", "total_enrollments"), ("attendance", "total_attendance"),
                               ("grades", "total_grades")]:
                try:
                    row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
                    overview[key] = row["cnt"]
                except sqlite3.OperationalError:
                    overview[key] = 0
            return overview
        finally:
            conn.close()
