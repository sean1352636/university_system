"""Pastoral service for tutor notes, wellbeing, and LAC records."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import PastoralError


class PastoralService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- Pastoral Notes ---

    def add_note(self, student_id: int, author_id: int, category: str,
                  content: str, is_confidential: int = 0,
                  follow_up_date: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO pastoral_notes
                   (student_id, author_id, category, content, is_confidential, follow_up_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (student_id, author_id, category, content, is_confidential, follow_up_date),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM pastoral_notes WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise PastoralError(f"Failed to add note: {e}")
        finally:
            conn.close()

    def list_notes(self, student_id: int = None, category: str = None,
                    limit: int = 100) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT pn.*, s.first_name, s.last_name
                       FROM pastoral_notes pn
                       LEFT JOIN students s ON pn.student_id = s.id WHERE 1=1"""
            params = []
            if student_id:
                query += " AND pn.student_id = ?"
                params.append(student_id)
            if category:
                query += " AND pn.category = ?"
                params.append(category)
            query += " ORDER BY pn.created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_note(self, note_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM pastoral_notes WHERE id = ?", (note_id,)).fetchone()
            if not row:
                raise PastoralError(f"Note {note_id} not found")
            return dict(row)
        finally:
            conn.close()

    # --- Wellbeing ---

    def record_wellbeing(self, student_id: int, recorded_by: int,
                          wellbeing_score: int = None, concerns: str = None,
                          actions: str = None,
                          referral_to: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO wellbeing_records
                   (student_id, recorded_by, wellbeing_score, concerns, actions, referral_to)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (student_id, recorded_by, wellbeing_score, concerns, actions, referral_to),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM wellbeing_records WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise PastoralError(f"Failed to record wellbeing: {e}")
        finally:
            conn.close()

    def list_wellbeing(self, student_id: int = None, limit: int = 50) -> list[dict]:
        conn = self._conn()
        try:
            if student_id:
                rows = conn.execute(
                    """SELECT wr.*, s.first_name, s.last_name FROM wellbeing_records wr
                       LEFT JOIN students s ON wr.student_id = s.id
                       WHERE wr.student_id = ? ORDER BY wr.record_date DESC LIMIT ?""",
                    (student_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT wr.*, s.first_name, s.last_name FROM wellbeing_records wr
                       LEFT JOIN students s ON wr.student_id = s.id
                       ORDER BY wr.record_date DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # --- LAC Records ---

    def create_lac_record(self, student_id: int, local_authority: str,
                           social_worker_name: str = None,
                           social_worker_contact: str = None,
                           care_status: str = "in_care",
                           pep_date: str = None, notes: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO lac_records
                   (student_id, local_authority, social_worker_name, social_worker_contact,
                    care_status, pep_date, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (student_id, local_authority, social_worker_name,
                 social_worker_contact, care_status, pep_date, notes),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM lac_records WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise PastoralError(f"Failed to create LAC record: {e}")
        finally:
            conn.close()

    def list_lac_records(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT lr.*, s.first_name, s.last_name FROM lac_records lr
                   LEFT JOIN students s ON lr.student_id = s.id
                   ORDER BY lr.created_at DESC"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_lac_record(self, record_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM lac_records WHERE id = ?", (record_id,)).fetchone()
            if not row:
                raise PastoralError(f"LAC record {record_id} not found")
            return dict(row)
        finally:
            conn.close()

    def update_lac_record(self, record_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"local_authority", "social_worker_name", "social_worker_contact",
                        "care_status", "pep_date", "notes"}
            parts, params = ["updated_at = datetime('now')"], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 2:
                raise PastoralError("No valid fields to update")
            params.append(record_id)
            conn.execute(f"UPDATE lac_records SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            return self.get_lac_record(record_id)
        except PastoralError:
            raise
        except Exception as e:
            raise PastoralError(f"Failed to update LAC record: {e}")
        finally:
            conn.close()
