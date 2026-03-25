"""Bursary service for managing bursary records and meal eligibility."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import BursaryError


class BursaryService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- Bursary Records ---

    def create_bursary(self, student_id: int, bursary_type: str = "discretionary",
                        amount: float = 0.0, evidence_type: str = None,
                        evidence_verified: int = 0,
                        payment_frequency: str = "one_off",
                        academic_year: str = None,
                        notes: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO bursary_records
                   (student_id, bursary_type, amount, evidence_type,
                    evidence_verified, payment_frequency, academic_year, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, bursary_type, amount, evidence_type,
                 evidence_verified, payment_frequency, academic_year, notes),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM bursary_records WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise BursaryError(f"Failed to create bursary record: {e}")
        finally:
            conn.close()

    def list_bursaries(self, status: str = None, bursary_type: str = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT br.*, s.first_name, s.last_name FROM bursary_records br
                       LEFT JOIN students s ON br.student_id = s.id WHERE 1=1"""
            params = []
            if status:
                query += " AND br.status = ?"
                params.append(status)
            if bursary_type:
                query += " AND br.bursary_type = ?"
                params.append(bursary_type)
            query += " ORDER BY s.last_name"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_bursary(self, bursary_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM bursary_records WHERE id = ?", (bursary_id,)
            ).fetchone()
            if not row:
                raise BursaryError(f"Bursary {bursary_id} not found")
            return dict(row)
        finally:
            conn.close()

    def update_bursary(self, bursary_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"status", "amount", "evidence_type", "evidence_verified",
                        "payment_frequency", "academic_year", "award_date",
                        "notes", "bursary_type"}
            parts, params = ["updated_at = datetime('now')"], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 2:
                raise BursaryError("No valid fields to update")
            params.append(bursary_id)
            conn.execute(f"UPDATE bursary_records SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            return self.get_bursary(bursary_id)
        except BursaryError:
            raise
        except Exception as e:
            raise BursaryError(f"Failed to update bursary: {e}")
        finally:
            conn.close()

    def get_student_bursary(self, student_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM bursary_records WHERE student_id = ? AND status = 'approved'",
                (student_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_application(self, application_id: int) -> bool:
        """Delete a bursary application by ID."""
        conn = self._conn()
        try:
            result = conn.execute(
                "DELETE FROM bursary_records WHERE id = ?", (application_id,)
            )
            conn.commit()
            if result.rowcount == 0:
                raise BursaryError(f"Bursary application {application_id} not found.")
            return True
        except BursaryError:
            raise
        except Exception as e:
            conn.rollback()
            raise BursaryError(f"Failed to delete bursary application: {e}")
        finally:
            conn.close()

    # --- Meal Eligibility ---

    def set_meal_eligibility(self, student_id: int, eligible: int = 1,
                               evidence_type: str = None,
                               verified_by: int = None) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM meal_eligibility WHERE student_id = ?", (student_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE meal_eligibility
                       SET eligible = ?, evidence_type = ?, verified_by = ?,
                           updated_at = datetime('now')
                       WHERE student_id = ?""",
                    (eligible, evidence_type, verified_by, student_id),
                )
            else:
                conn.execute(
                    """INSERT INTO meal_eligibility
                       (student_id, eligible, evidence_type, verified_by)
                       VALUES (?, ?, ?, ?)""",
                    (student_id, eligible, evidence_type, verified_by),
                )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM meal_eligibility WHERE student_id = ?", (student_id,)
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise BursaryError(f"Failed to set meal eligibility: {e}")
        finally:
            conn.close()

    def list_meal_eligible(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT me.*, s.first_name, s.last_name FROM meal_eligibility me
                   LEFT JOIN students s ON me.student_id = s.id
                   WHERE me.eligible = 1
                   ORDER BY s.last_name"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def check_eligibility(self, student_id: int) -> bool:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT eligible FROM meal_eligibility WHERE student_id = ?",
                (student_id,),
            ).fetchone()
            return bool(row and row["eligible"])
        finally:
            conn.close()
