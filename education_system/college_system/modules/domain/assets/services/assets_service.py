"""Assets service for managing equipment and device loans."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import AssetsError


class AssetsService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_loan(self, description: str, asset_tag: str, student_id: int,
                     asset_type: str = "laptop", condition_out: str = "good",
                     recorded_by: int = None, notes: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO asset_loans
                   (description, asset_tag, asset_type, student_id,
                    condition_out, recorded_by, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (description, asset_tag, asset_type, student_id,
                 condition_out, recorded_by, notes),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM asset_loans WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise AssetsError(f"Failed to create loan: {e}")
        finally:
            conn.close()

    def list_loans(self, status: str = None, asset_type: str = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT al.*, s.first_name, s.last_name FROM asset_loans al
                       LEFT JOIN students s ON al.student_id = s.id WHERE 1=1"""
            params = []
            if status:
                query += " AND al.status = ?"
                params.append(status)
            if asset_type:
                query += " AND al.asset_type = ?"
                params.append(asset_type)
            query += " ORDER BY al.loaned_date DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_loan(self, loan_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT al.*, s.first_name, s.last_name FROM asset_loans al
                   LEFT JOIN students s ON al.student_id = s.id WHERE al.id = ?""",
                (loan_id,),
            ).fetchone()
            if not row:
                raise AssetsError(f"Loan {loan_id} not found")
            return dict(row)
        finally:
            conn.close()

    def return_asset(self, loan_id: int, condition_in: str = "good",
                      notes: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """UPDATE asset_loans
                   SET status = 'returned', returned_date = date('now'),
                       condition_in = ?, notes = COALESCE(?, notes)
                   WHERE id = ?""",
                (condition_in, notes, loan_id),
            )
            conn.commit()
            return self.get_loan(loan_id)
        except AssetsError:
            raise
        except Exception as e:
            raise AssetsError(f"Failed to return asset: {e}")
        finally:
            conn.close()

    def update_loan(self, loan_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"status", "returned_date", "condition_in", "notes",
                        "due_date"}
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if not parts:
                raise AssetsError("No valid fields to update")
            params.append(loan_id)
            conn.execute(f"UPDATE asset_loans SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            return self.get_loan(loan_id)
        except AssetsError:
            raise
        except Exception as e:
            raise AssetsError(f"Failed to update loan: {e}")
        finally:
            conn.close()

    def get_student_loans(self, student_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM asset_loans WHERE student_id = ? ORDER BY loaned_date DESC",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_asset(self, asset_id: int) -> bool:
        """Delete an asset loan record by ID."""
        conn = self._conn()
        try:
            result = conn.execute(
                "DELETE FROM asset_loans WHERE id = ?", (asset_id,)
            )
            conn.commit()
            if result.rowcount == 0:
                raise AssetsError(f"Asset {asset_id} not found.")
            return True
        except AssetsError:
            raise
        except Exception as e:
            conn.rollback()
            raise AssetsError(f"Failed to delete asset: {e}")
        finally:
            conn.close()

    def count_active_loans(self) -> int:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM asset_loans WHERE status = 'on_loan'"
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()
