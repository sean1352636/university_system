"""Staff Absence service."""

from education_system.college_system.core.exceptions import StaffAbsenceError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class StaffAbsenceService:
    """Staff Absence service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ---- Absences ----

    def create_absence(self, staff_id: int, start_date: str, **kwargs) -> dict:
        conn = self._conn()
        try:
            fields = {"staff_id": staff_id, "start_date": start_date}
            allowed = {
                "absence_type", "end_date", "days_lost", "reason",
                "self_certified", "fit_note_received", "fit_note_expiry",
                "return_to_work_done", "rtw_date", "rtw_notes",
                "occupational_health_referral", "trigger_point_reached",
                "status", "notes",
            }
            for k, v in kwargs.items():
                if k in allowed and v is not None:
                    fields[k] = v
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            vals = list(fields.values())
            conn.execute(
                f"INSERT INTO staff_absences ({cols}) VALUES ({placeholders})", vals
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM staff_absences WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise StaffAbsenceError(f"Failed to create absence: {e}") from e
        finally:
            conn.close()

    def list_absences(self, staff_id: int = None, absence_type: str = None,
                      status: str = None, search: str = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT sa.*,
                              s.first_name, s.last_name
                       FROM staff_absences sa
                       LEFT JOIN staff s ON sa.staff_id = s.id
                       WHERE 1=1"""
            params: list = []
            if staff_id is not None:
                query += " AND sa.staff_id = ?"
                params.append(staff_id)
            if absence_type:
                query += " AND sa.absence_type = ?"
                params.append(absence_type)
            if status:
                query += " AND sa.status = ?"
                params.append(status)
            if search:
                query += (" AND (s.first_name LIKE ? OR s.last_name LIKE ?"
                          " OR sa.reason LIKE ? OR sa.notes LIKE ?)")
                term = f"%{search}%"
                params.extend([term, term, term, term])
            query += " ORDER BY sa.start_date DESC, sa.id DESC"
            return [dict(r) for r in conn.execute(query, params).fetchall()]
        finally:
            conn.close()

    def get_absence(self, absence_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT sa.*, s.first_name, s.last_name
                   FROM staff_absences sa
                   LEFT JOIN staff s ON sa.staff_id = s.id
                   WHERE sa.id = ?""",
                (absence_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_absence(self, absence_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {
                "absence_type", "start_date", "end_date", "days_lost", "reason",
                "self_certified", "fit_note_received", "fit_note_expiry",
                "return_to_work_done", "rtw_date", "rtw_notes",
                "occupational_health_referral", "trigger_point_reached",
                "status", "notes",
            }
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if not parts:
                raise StaffAbsenceError("No valid fields to update.")
            parts.append("updated_at = datetime('now')")
            params.append(absence_id)
            conn.execute(
                f"UPDATE staff_absences SET {', '.join(parts)} WHERE id = ?", params
            )
            conn.commit()
            return self.get_absence(absence_id)
        except StaffAbsenceError:
            raise
        except Exception as e:
            conn.rollback()
            raise StaffAbsenceError(f"Failed to update absence: {e}") from e
        finally:
            conn.close()

    def delete_absence(self, absence_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM staff_absences WHERE id = ?", (absence_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise StaffAbsenceError(f"Failed to delete absence: {e}") from e
        finally:
            conn.close()

    def close_absence(self, absence_id: int, end_date: str, days_lost: float,
                      rtw_notes: str = None) -> dict:
        conn = self._conn()
        try:
            fields = {
                "end_date": end_date,
                "days_lost": days_lost,
                "status": "closed",
                "return_to_work_done": 1,
                "rtw_date": "datetime('now')",
            }
            sql = """UPDATE staff_absences
                     SET end_date = ?, days_lost = ?, status = 'closed',
                         return_to_work_done = 1, rtw_date = datetime('now'),
                         rtw_notes = ?, updated_at = datetime('now')
                     WHERE id = ?"""
            conn.execute(sql, (end_date, days_lost, rtw_notes, absence_id))
            conn.commit()
            return self.get_absence(absence_id)
        except Exception as e:
            conn.rollback()
            raise StaffAbsenceError(f"Failed to close absence: {e}") from e
        finally:
            conn.close()

    # ---- Triggers ----

    def create_trigger(self, trigger_name: str, threshold: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            fields = {"trigger_name": trigger_name, "threshold": threshold}
            allowed = {"trigger_type", "period_months", "action_required", "status"}
            for k, v in kwargs.items():
                if k in allowed and v is not None:
                    fields[k] = v
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            vals = list(fields.values())
            conn.execute(
                f"INSERT INTO staff_absence_triggers ({cols}) VALUES ({placeholders})",
                vals,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM staff_absence_triggers WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise StaffAbsenceError(f"Failed to create trigger: {e}") from e
        finally:
            conn.close()

    def list_triggers(self, status: str = None) -> list[dict]:
        conn = self._conn()
        try:
            query = "SELECT * FROM staff_absence_triggers WHERE 1=1"
            params: list = []
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY trigger_name"
            return [dict(r) for r in conn.execute(query, params).fetchall()]
        finally:
            conn.close()

    def get_trigger(self, trigger_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM staff_absence_triggers WHERE id = ?", (trigger_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_trigger(self, trigger_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"trigger_name", "trigger_type", "threshold",
                       "period_months", "action_required", "status"}
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if not parts:
                raise StaffAbsenceError("No valid fields to update.")
            params.append(trigger_id)
            conn.execute(
                f"UPDATE staff_absence_triggers SET {', '.join(parts)} WHERE id = ?",
                params,
            )
            conn.commit()
            return self.get_trigger(trigger_id)
        except StaffAbsenceError:
            raise
        except Exception as e:
            conn.rollback()
            raise StaffAbsenceError(f"Failed to update trigger: {e}") from e
        finally:
            conn.close()

    def delete_trigger(self, trigger_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM staff_absence_triggers WHERE id = ?", (trigger_id,)
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise StaffAbsenceError(f"Failed to delete trigger: {e}") from e
        finally:
            conn.close()

    # ---- Analysis ----

    def check_triggers(self, staff_id: int) -> list[dict]:
        conn = self._conn()
        try:
            triggers = conn.execute(
                "SELECT * FROM staff_absence_triggers WHERE status = 'active'"
            ).fetchall()
            breached: list[dict] = []
            for t in triggers:
                t = dict(t)
                period = t.get("period_months", 12) or 12
                if t.get("trigger_type") == "days":
                    row = conn.execute(
                        """SELECT COALESCE(SUM(days_lost), 0) as total
                           FROM staff_absences
                           WHERE staff_id = ?
                             AND start_date >= date('now', ?)""",
                        (staff_id, f"-{period} months"),
                    ).fetchone()
                    total = row["total"] if row else 0
                    if total >= t["threshold"]:
                        t["actual_value"] = total
                        breached.append(t)
                elif t.get("trigger_type") == "occasions":
                    row = conn.execute(
                        """SELECT COUNT(*) as cnt
                           FROM staff_absences
                           WHERE staff_id = ?
                             AND start_date >= date('now', ?)""",
                        (staff_id, f"-{period} months"),
                    ).fetchone()
                    cnt = row["cnt"] if row else 0
                    if cnt >= t["threshold"]:
                        t["actual_value"] = cnt
                        breached.append(t)
            return breached
        finally:
            conn.close()

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM staff_absences"
            ).fetchone()["cnt"]
            current = conn.execute(
                "SELECT COUNT(*) as cnt FROM staff_absences WHERE status = 'current'"
            ).fetchone()["cnt"]
            closed = conn.execute(
                "SELECT COUNT(*) as cnt FROM staff_absences WHERE status = 'closed'"
            ).fetchone()["cnt"]
            days_row = conn.execute(
                "SELECT COALESCE(SUM(days_lost), 0) as total FROM staff_absences"
            ).fetchone()
            total_days_lost = days_row["total"]

            by_type_rows = conn.execute(
                """SELECT absence_type, COUNT(*) as cnt,
                          COALESCE(SUM(days_lost), 0) as days
                   FROM staff_absences
                   GROUP BY absence_type
                   ORDER BY cnt DESC"""
            ).fetchall()
            by_type = [dict(r) for r in by_type_rows]

            active_triggers = conn.execute(
                "SELECT COUNT(*) as cnt FROM staff_absence_triggers WHERE status = 'active'"
            ).fetchone()["cnt"]

            staff_on_absence = conn.execute(
                "SELECT COUNT(DISTINCT staff_id) as cnt FROM staff_absences WHERE status = 'current'"
            ).fetchone()["cnt"]

            return {
                "total_absences": total,
                "current": current,
                "closed": closed,
                "total_days_lost": total_days_lost,
                "by_type": by_type,
                "active_triggers": active_triggers,
                "staff_on_absence": staff_on_absence,
            }
        finally:
            conn.close()
