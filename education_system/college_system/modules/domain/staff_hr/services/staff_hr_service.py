"""Staff HR service for managing HR records."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import StaffHRError


class StaffHRService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_record(self, staff_id: int,
                       contract_type: str = "full_time",
                       contract_start: str = None,
                       contract_end: str = None,
                       dbs_number: str = None,
                       dbs_date: str = None,
                       dbs_status: str = "pending",
                       safeguarding_training_date: str = None,
                       safeguarding_training_expiry: str = None,
                       first_aid_trained: int = 0,
                       prevent_trained: int = 0,
                       notes: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO staff_hr
                   (staff_id, contract_type, contract_start, contract_end,
                    dbs_number, dbs_date, dbs_status,
                    safeguarding_training_date, safeguarding_training_expiry,
                    first_aid_trained, prevent_trained, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (staff_id, contract_type, contract_start, contract_end,
                 dbs_number, dbs_date, dbs_status,
                 safeguarding_training_date, safeguarding_training_expiry,
                 first_aid_trained, prevent_trained, notes),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM staff_hr WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise StaffHRError(f"Failed to create HR record: {e}")
        finally:
            conn.close()

    def list_records(self, contract_type: str = None,
                      dbs_status: str = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT sh.*, s.first_name, s.last_name FROM staff_hr sh
                       LEFT JOIN staff s ON sh.staff_id = s.id WHERE 1=1"""
            params = []
            if contract_type:
                query += " AND sh.contract_type = ?"
                params.append(contract_type)
            if dbs_status:
                query += " AND sh.dbs_status = ?"
                params.append(dbs_status)
            query += " ORDER BY s.last_name"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_record(self, record_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT sh.*, s.first_name, s.last_name FROM staff_hr sh
                   LEFT JOIN staff s ON sh.staff_id = s.id WHERE sh.id = ?""",
                (record_id,),
            ).fetchone()
            if not row:
                raise StaffHRError(f"HR record {record_id} not found")
            return dict(row)
        finally:
            conn.close()

    def get_by_staff(self, staff_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM staff_hr WHERE staff_id = ?", (staff_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_record(self, record_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"contract_type", "contract_start", "contract_end",
                        "dbs_number", "dbs_date", "dbs_status",
                        "safeguarding_training_date", "safeguarding_training_expiry",
                        "first_aid_trained", "prevent_trained", "notes"}
            parts, params = ["updated_at = datetime('now')"], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 2:
                raise StaffHRError("No valid fields to update")
            params.append(record_id)
            conn.execute(f"UPDATE staff_hr SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            return self.get_record(record_id)
        except StaffHRError:
            raise
        except Exception as e:
            raise StaffHRError(f"Failed to update HR record: {e}")
        finally:
            conn.close()

    def count_staff(self) -> int:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM staff_hr"
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()
