"""DBS Checks service for managing DBS/disclosure checks for staff, governors, and volunteers."""

from education_system.college_system.core.exceptions import DBSCheckError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class DBSCheckService:
    """DBS Checks management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_check(self, *, staff_id: int = None, governor_id: int = None,
                     volunteer_name: str = None, check_type: str = "enhanced",
                     certificate_number: str = None, issue_date: str = None,
                     expiry_date: str = None, update_service: int = 0,
                     update_service_id: str = None,
                     barred_list_checked: int = 0,
                     children_workforce: int = 1,
                     status: str = "valid", notes: str = None) -> dict:
        if not staff_id and not governor_id and not volunteer_name:
            raise DBSCheckError("Must specify staff_id, governor_id, or volunteer_name.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO dbs_checks
                   (staff_id, governor_id, volunteer_name, check_type,
                    certificate_number, issue_date, expiry_date,
                    update_service, update_service_id, barred_list_checked,
                    children_workforce, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (staff_id, governor_id, volunteer_name, check_type,
                 certificate_number, issue_date, expiry_date,
                 update_service, update_service_id, barred_list_checked,
                 children_workforce, status, notes))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM dbs_checks WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except DBSCheckError:
            raise
        except Exception as e:
            conn.rollback()
            raise DBSCheckError(f"Failed to create DBS check: {e}") from e
        finally:
            conn.close()

    def list_checks(self, *, status: str = None, check_type: str = None,
                    expiring_before: str = None, search: str = None,
                    limit: int = 200) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM dbs_checks WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if check_type:
                sql += " AND check_type = ?"
                params.append(check_type)
            if expiring_before:
                sql += " AND expiry_date IS NOT NULL AND expiry_date <= ?"
                params.append(expiring_before)
            if search:
                sql += (" AND (volunteer_name LIKE ? OR certificate_number LIKE ?"
                        " OR CAST(staff_id AS TEXT) LIKE ?)")
                term = f"%{search}%"
                params.extend([term, term, term])
            sql += " ORDER BY expiry_date ASC NULLS LAST, created_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_check(self, check_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM dbs_checks WHERE id = ?", (check_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_check(self, check_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {
                "staff_id", "governor_id", "volunteer_name", "check_type",
                "certificate_number", "issue_date", "expiry_date",
                "update_service", "update_service_id", "barred_list_checked",
                "children_workforce", "status", "notes",
            }
            parts, params = ["updated_at = datetime('now')"], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 2:
                raise DBSCheckError("No valid fields to update.")
            params.append(check_id)
            conn.execute(
                f"UPDATE dbs_checks SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            return self.get_check(check_id)
        except DBSCheckError:
            raise
        except Exception as e:
            conn.rollback()
            raise DBSCheckError(f"Failed to update DBS check: {e}") from e
        finally:
            conn.close()

    def delete_check(self, check_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM dbs_checks WHERE id = ?", (check_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise DBSCheckError(f"Failed to delete DBS check: {e}") from e
        finally:
            conn.close()

    def get_expiring(self, within_days: int = 90) -> list[dict]:
        """Get checks expiring within N days."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM dbs_checks
                   WHERE expiry_date IS NOT NULL
                     AND status = 'valid'
                     AND expiry_date <= date('now', '+' || ? || ' days')
                   ORDER BY expiry_date ASC""",
                (within_days,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM dbs_checks").fetchone()[0]
            valid = conn.execute(
                "SELECT COUNT(*) FROM dbs_checks WHERE status = 'valid'"
            ).fetchone()[0]
            expired = conn.execute(
                "SELECT COUNT(*) FROM dbs_checks WHERE status = 'expired'"
            ).fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM dbs_checks WHERE status = 'pending'"
            ).fetchone()[0]
            on_update = conn.execute(
                "SELECT COUNT(*) FROM dbs_checks WHERE update_service = 1"
            ).fetchone()[0]
            expiring_90 = conn.execute(
                """SELECT COUNT(*) FROM dbs_checks
                   WHERE expiry_date IS NOT NULL AND status = 'valid'
                     AND expiry_date <= date('now', '+90 days')"""
            ).fetchone()[0]
            by_type = {}
            for row in conn.execute(
                "SELECT check_type, COUNT(*) as cnt FROM dbs_checks GROUP BY check_type"
            ).fetchall():
                by_type[row["check_type"]] = row["cnt"]
            return {
                "total": total, "valid": valid, "expired": expired,
                "pending": pending, "on_update_service": on_update,
                "expiring_90_days": expiring_90, "by_type": by_type,
            }
        finally:
            conn.close()
