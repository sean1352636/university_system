"""Attendance management service."""

from datetime import date, datetime, timedelta
import logging

from education_system.secondary_school.core.exceptions import AttendanceError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class AttendanceService:
    """Service for managing attendance records."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def record_attendance(self, student_id: int, date_str: str, status: str = "present",
                          subject_id: int | None = None, period: str | None = None,
                          note: str | None = None, recorded_by: str | None = None) -> dict:
        """Record an attendance entry."""
        conn = self._conn()
        try:
            # Check for duplicate
            existing = conn.execute(
                """SELECT id FROM attendance_records
                   WHERE student_id = ? AND date = ? AND period = ? AND subject_id IS ?""",
                (student_id, date_str, period, subject_id),
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE attendance_records SET status = ?, note = ?, recorded_by = ? WHERE id = ?",
                    (status, note, recorded_by, existing["id"]),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM attendance_records WHERE id = ?", (existing["id"],)
                ).fetchone()
            else:
                cursor = conn.execute(
                    """INSERT INTO attendance_records
                       (student_id, subject_id, date, period, status, note, recorded_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (student_id, subject_id, date_str, period, status, note, recorded_by),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM attendance_records WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()

            return dict(row)
        except Exception as e:
            conn.rollback()
            raise AttendanceError(f"Failed to record attendance: {e}") from e
        finally:
            conn.close()

    def get_student_attendance(self, student_id: int, start_date: str | None = None,
                               end_date: str | None = None) -> list[dict]:
        sql = "SELECT * FROM attendance_records WHERE student_id = ?"
        params: list = [student_id]

        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)

        sql += " ORDER BY date DESC, period"

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_attendance_by_date(self, date_str: str, subject_id: int | None = None,
                               year_group: str | None = None) -> list[dict]:
        sql = """SELECT ar.*, s.student_id as sid, s.first_name, s.last_name,
                        s.year_group, s.form_group
                 FROM attendance_records ar JOIN students s ON ar.student_id = s.id
                 WHERE ar.date = ?"""
        params: list = [date_str]

        if subject_id:
            sql += " AND ar.subject_id = ?"
            params.append(subject_id)
        if year_group:
            sql += " AND s.year_group = ?"
            params.append(year_group)

        sql += " ORDER BY s.last_name"

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_attendance_summary(self, student_id: int) -> dict:
        """Get attendance summary stats for a student."""
        conn = self._conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM attendance_records WHERE student_id = ?",
                (student_id,),
            ).fetchone()["cnt"]

            if total == 0:
                return {"total": 0, "present": 0, "absent": 0, "late": 0, "percentage": 0.0}

            present = conn.execute(
                "SELECT COUNT(*) as cnt FROM attendance_records WHERE student_id = ? AND status = 'present'",
                (student_id,),
            ).fetchone()["cnt"]

            absent = conn.execute(
                "SELECT COUNT(*) as cnt FROM attendance_records WHERE student_id = ? AND status IN ('absent', 'unauthorised_absent')",
                (student_id,),
            ).fetchone()["cnt"]

            late = conn.execute(
                "SELECT COUNT(*) as cnt FROM attendance_records WHERE student_id = ? AND status = 'late'",
                (student_id,),
            ).fetchone()["cnt"]

            percentage = round((present + late) / total * 100, 1) if total else 0.0

            return {
                "total": total,
                "present": present,
                "absent": absent,
                "late": late,
                "percentage": percentage,
            }
        finally:
            conn.close()

    def check_duplicate_entry(self, date_str: str, period: str, year_group: str) -> bool:
        """Check if attendance already recorded for this date/period/year group."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM attendance_records ar
                   JOIN students s ON ar.student_id = s.id
                   WHERE ar.date = ? AND ar.period = ? AND s.year_group = ?""",
                (date_str, period, year_group),
            ).fetchone()
            return row["cnt"] > 0
        finally:
            conn.close()

    def get_weekly_summary(self, year_group: str, week_start: str) -> list[dict]:
        """Get attendance summary for a week starting from week_start."""
        conn = self._conn()
        try:
            start = datetime.strptime(week_start, "%Y-%m-%d").date()
            end = start + timedelta(days=4)
            rows = conn.execute(
                """SELECT ar.date, ar.status, COUNT(*) as cnt
                   FROM attendance_records ar
                   JOIN students s ON ar.student_id = s.id
                   WHERE s.year_group = ? AND ar.date >= ? AND ar.date <= ?
                   GROUP BY ar.date, ar.status
                   ORDER BY ar.date""",
                (year_group, start.isoformat(), end.isoformat()),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_persistent_absentees(self, year_group: str, consecutive_days: int = 3) -> list[dict]:
        """Find students absent for consecutive_days or more in a row."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT s.id, s.student_id, s.first_name, s.last_name, s.form_group,
                          COUNT(DISTINCT ar.date) as absent_days
                   FROM attendance_records ar
                   JOIN students s ON ar.student_id = s.id
                   WHERE s.year_group = ?
                     AND ar.status IN ('absent', 'unauthorised_absent')
                     AND ar.date >= date('now', ?)
                   GROUP BY s.id
                   HAVING absent_days >= ?
                   ORDER BY absent_days DESC""",
                (year_group, f"-{consecutive_days + 5} days", consecutive_days),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_audit_log(self, date_str: str | None = None, year_group: str | None = None,
                      limit: int = 100) -> list[dict]:
        """Get audit log of attendance records (who saved what and when)."""
        sql = """SELECT ar.id, ar.date, ar.period, ar.status, ar.recorded_by,
                        ar.note, s.student_id as sid, s.first_name, s.last_name
                 FROM attendance_records ar
                 JOIN students s ON ar.student_id = s.id WHERE 1=1"""
        params: list = []
        if date_str:
            sql += " AND ar.date = ?"
            params.append(date_str)
        if year_group:
            sql += " AND s.year_group = ?"
            params.append(year_group)
        sql += " ORDER BY ar.id DESC LIMIT ?"
        params.append(limit)
        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def import_from_csv(self, rows: list[dict], recorded_by: str = "csv_import") -> dict:
        """Import attendance from a list of dicts with student_id, date, period, status."""
        imported = 0
        errors = 0
        for row in rows:
            try:
                self.record_attendance(
                    student_id=int(row["student_id"]),
                    date_str=row["date"],
                    status=row.get("status", "present"),
                    period=row.get("period", "AM"),
                    note=row.get("note"),
                    recorded_by=recorded_by,
                )
                imported += 1
            except Exception:
                errors += 1
        return {"imported": imported, "errors": errors}

    def get_all_student_percentages(self, year_group: str) -> list[dict]:
        """Get attendance percentage for every student in a year group (YTD)."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT s.id, s.student_id, s.first_name, s.last_name, s.form_group,
                          COUNT(ar.id) as total,
                          SUM(CASE WHEN ar.status IN ('present', 'late') THEN 1 ELSE 0 END) as attended
                   FROM students s
                   LEFT JOIN attendance_records ar ON ar.student_id = s.id
                   WHERE s.year_group = ? AND s.status = 'active'
                   GROUP BY s.id
                   ORDER BY s.last_name""",
                (year_group,),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["percentage"] = round(d["attended"] / d["total"] * 100, 1) if d["total"] else 0.0
                result.append(d)
            return result
        finally:
            conn.close()

    def get_day_pattern_absences(self, year_group: str, min_count: int = 3) -> list[dict]:
        """Find students frequently absent on a specific day of the week."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT s.id, s.student_id, s.first_name, s.last_name,
                          CASE CAST(strftime('%%w', ar.date) AS INTEGER)
                            WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday'
                            WHEN 3 THEN 'Wednesday' WHEN 4 THEN 'Thursday' WHEN 5 THEN 'Friday'
                            WHEN 6 THEN 'Saturday' END as day_name,
                          COUNT(*) as absence_count
                   FROM attendance_records ar
                   JOIN students s ON ar.student_id = s.id
                   WHERE s.year_group = ? AND ar.status IN ('absent', 'unauthorised_absent')
                   GROUP BY s.id, day_name
                   HAVING absence_count >= ?
                   ORDER BY absence_count DESC""",
                (year_group, min_count),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def compare_year_groups(self) -> list[dict]:
        """Get attendance rates per year group."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT s.year_group,
                          COUNT(ar.id) as total,
                          SUM(CASE WHEN ar.status IN ('present', 'late') THEN 1 ELSE 0 END) as attended
                   FROM attendance_records ar
                   JOIN students s ON ar.student_id = s.id
                   WHERE s.status = 'active'
                   GROUP BY s.year_group
                   ORDER BY s.year_group"""
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["percentage"] = round(d["attended"] / d["total"] * 100, 1) if d["total"] else 0.0
                result.append(d)
            return result
        finally:
            conn.close()

    def get_form_group_rates(self, year_group: str) -> list[dict]:
        """Rank form groups by attendance rate."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT s.form_group,
                          COUNT(ar.id) as total,
                          SUM(CASE WHEN ar.status IN ('present', 'late') THEN 1 ELSE 0 END) as attended
                   FROM attendance_records ar
                   JOIN students s ON ar.student_id = s.id
                   WHERE s.year_group = ? AND s.status = 'active'
                   GROUP BY s.form_group
                   ORDER BY attended * 1.0 / CASE WHEN total = 0 THEN 1 ELSE total END DESC""",
                (year_group,),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["percentage"] = round(d["attended"] / d["total"] * 100, 1) if d["total"] else 0.0
                result.append(d)
            return result
        finally:
            conn.close()

    def get_attendance_trend(self, year_group: str, days: int = 60) -> list[dict]:
        """Get daily attendance rate over the past N days."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT ar.date,
                          COUNT(ar.id) as total,
                          SUM(CASE WHEN ar.status IN ('present', 'late') THEN 1 ELSE 0 END) as attended
                   FROM attendance_records ar
                   JOIN students s ON ar.student_id = s.id
                   WHERE s.year_group = ? AND ar.date >= date('now', ?)
                   GROUP BY ar.date
                   ORDER BY ar.date""",
                (year_group, f"-{days} days"),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["percentage"] = round(d["attended"] / d["total"] * 100, 1) if d["total"] else 0.0
                result.append(d)
            return result
        finally:
            conn.close()

    def get_monday_friday_absences(self, year_group: str) -> list[dict]:
        """Find students disproportionately absent on Mon/Fri."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT s.id, s.student_id, s.first_name, s.last_name,
                          SUM(CASE WHEN CAST(strftime('%%w', ar.date) AS INTEGER) IN (1, 5) THEN 1 ELSE 0 END) as mon_fri_abs,
                          COUNT(*) as total_abs
                   FROM attendance_records ar
                   JOIN students s ON ar.student_id = s.id
                   WHERE s.year_group = ? AND ar.status IN ('absent', 'unauthorised_absent')
                   GROUP BY s.id
                   HAVING total_abs >= 3 AND mon_fri_abs * 1.0 / total_abs > 0.6
                   ORDER BY mon_fri_abs DESC""",
                (year_group,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_punctuality_stats(self, year_group: str) -> dict:
        """Breakdown of late vs on-time arrivals."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT
                     SUM(CASE WHEN ar.status = 'present' THEN 1 ELSE 0 END) as on_time,
                     SUM(CASE WHEN ar.status = 'late' THEN 1 ELSE 0 END) as late,
                     COUNT(ar.id) as total
                   FROM attendance_records ar
                   JOIN students s ON ar.student_id = s.id
                   WHERE s.year_group = ? AND ar.status IN ('present', 'late')""",
                (year_group,),
            ).fetchone()
            d = dict(row)
            d["on_time_pct"] = round(d["on_time"] / d["total"] * 100, 1) if d["total"] else 0.0
            d["late_pct"] = round(d["late"] / d["total"] * 100, 1) if d["total"] else 0.0
            return d
        finally:
            conn.close()

    def get_students_below_threshold(self, year_group: str, threshold: float = 90.0) -> list[dict]:
        """Get students whose attendance percentage is below threshold."""
        all_pcts = self.get_all_student_percentages(year_group)
        return [s for s in all_pcts if s["percentage"] < threshold]

    def get_student_heatmap_data(self, student_id: int, start_date: str | None = None,
                                  end_date: str | None = None) -> list[dict]:
        """Get attendance records formatted for calendar heatmap display."""
        conn = self._conn()
        try:
            sql = """SELECT date, status, period FROM attendance_records
                     WHERE student_id = ?"""
            params: list = [student_id]
            if start_date:
                sql += " AND date >= ?"
                params.append(start_date)
            if end_date:
                sql += " AND date <= ?"
                params.append(end_date)
            sql += " ORDER BY date"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_attendance_by_subject(self, subject_id: int, date_str: str | None = None) -> list[dict]:
        """Get attendance records filtered by subject."""
        conn = self._conn()
        try:
            sql = """SELECT ar.*, s.student_id as sid, s.first_name, s.last_name,
                            s.year_group, s.form_group
                     FROM attendance_records ar JOIN students s ON ar.student_id = s.id
                     WHERE ar.subject_id = ?"""
            params: list = [subject_id]
            if date_str:
                sql += " AND ar.date = ?"
                params.append(date_str)
            sql += " ORDER BY s.last_name"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_communication_log(self, student_id: int) -> list[dict]:
        """Get communication log entries for a student (absence-related)."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM communication_log
                   WHERE student_id = ? ORDER BY created_at DESC""",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []
        finally:
            conn.close()

    def log_communication(self, student_id: int, comm_type: str, message: str,
                          recorded_by: str) -> dict | None:
        """Log a communication entry (phone call, email, letter)."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO communication_log
                   (student_id, type, message, recorded_by, created_at)
                   VALUES (?, ?, ?, ?, datetime('now'))""",
                (student_id, comm_type, message, recorded_by),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM communication_log WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row) if row else None
        except Exception:
            conn.rollback()
            return None
        finally:
            conn.close()
