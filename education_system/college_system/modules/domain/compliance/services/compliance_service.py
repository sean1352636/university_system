"""Compliance service for funding, resit tracking, and destination data."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import ComplianceError
from education_system.college_system.core.sql_safety import validate_identifier


class ComplianceService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- Funding Records ---

    def create_funding_record(self, student_id: int, learning_aim: str,
                                funding_model: str, aim_type: str = None,
                                planned_hours: int = None,
                                start_date: str = None) -> dict:
        conn = self._conn()
        try:
            fields = {k: v for k, v in {
                'student_id': student_id, 'learning_aim': learning_aim,
                'funding_model': funding_model, 'aim_type': aim_type,
                'planned_hours': planned_hours, 'start_date': start_date,
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO funding_records ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM funding_records WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise ComplianceError(f"Failed to create funding record: {e}")
        finally:
            conn.close()

    def list_funding_records(self, student_id: int = None) -> list[dict]:
        conn = self._conn()
        try:
            if student_id:
                rows = conn.execute(
                    """SELECT fr.*, s.first_name, s.last_name FROM funding_records fr
                       LEFT JOIN students s ON fr.student_id = s.id
                       WHERE fr.student_id = ?""",
                    (student_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT fr.*, s.first_name, s.last_name FROM funding_records fr
                       LEFT JOIN students s ON fr.student_id = s.id
                       ORDER BY s.last_name"""
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_funding_record(self, record_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"completion_status", "aim_type",
                        "planned_hours", "actual_hours", "start_date",
                        "planned_end_date", "actual_end_date", "outcome",
                        "withdrawal_reason"}
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{validate_identifier(k)} = ?")
                    params.append(v)
            if not parts:
                raise ComplianceError("No valid fields to update")
            params.append(record_id)
            conn.execute(f"UPDATE funding_records SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            row = conn.execute("SELECT * FROM funding_records WHERE id = ?", (record_id,)).fetchone()
            return dict(row) if row else {}
        except ComplianceError:
            raise
        except Exception as e:
            raise ComplianceError(f"Failed to update funding record: {e}")
        finally:
            conn.close()

    def delete_record(self, record_id: int) -> bool:
        """Delete a funding record by ID."""
        conn = self._conn()
        try:
            result = conn.execute(
                "DELETE FROM funding_records WHERE id = ?", (record_id,)
            )
            conn.commit()
            if result.rowcount == 0:
                raise ComplianceError(f"Funding record {record_id} not found.")
            return True
        except ComplianceError:
            raise
        except Exception as e:
            conn.rollback()
            raise ComplianceError(f"Failed to delete funding record: {e}")
        finally:
            conn.close()

    # --- Resit Tracking ---

    def create_resit(self, student_id: int, subject: str,
                      gcse_grade_on_entry: str = None,
                      target_grade: str = None,
                      resit_required: int = 1) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO resit_tracking
                   (student_id, subject, gcse_grade_on_entry, target_grade,
                    resit_required)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, subject, gcse_grade_on_entry, target_grade,
                 resit_required),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM resit_tracking WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise ComplianceError(f"Failed to create resit record: {e}")
        finally:
            conn.close()

    def list_resits(self, student_id: int = None, status: str = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT rt.*, s.first_name, s.last_name FROM resit_tracking rt
                       LEFT JOIN students s ON rt.student_id = s.id WHERE 1=1"""
            params = []
            if student_id:
                query += " AND rt.student_id = ?"
                params.append(student_id)
            if status:
                query += " AND rt.status = ?"
                params.append(status)
            query += " ORDER BY rt.created_at DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_resit(self, resit_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"status", "latest_result", "target_grade", "notes",
                        "current_level", "exam_entries_count"}
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{validate_identifier(k)} = ?")
                    params.append(v)
            if not parts:
                raise ComplianceError("No valid fields to update")
            params.append(resit_id)
            conn.execute(f"UPDATE resit_tracking SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            row = conn.execute("SELECT * FROM resit_tracking WHERE id = ?", (resit_id,)).fetchone()
            return dict(row) if row else {}
        except ComplianceError:
            raise
        except Exception as e:
            raise ComplianceError(f"Failed to update resit: {e}")
        finally:
            conn.close()

    # --- Destinations ---

    def create_destination(self, student_id: int, destination_type: str,
                            institution_name: str = None, course_title: str = None,
                            contact_made: int = 0, notes: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO destinations
                   (student_id, destination_type, institution_name, course_title,
                    contact_made, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (student_id, destination_type, institution_name, course_title,
                 contact_made, notes),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM destinations WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise ComplianceError(f"Failed to create destination: {e}")
        finally:
            conn.close()

    def list_destinations(self, destination_type: str = None,
                           contact_made: int = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT d.*, s.first_name, s.last_name FROM destinations d
                       LEFT JOIN students s ON d.student_id = s.id WHERE 1=1"""
            params = []
            if destination_type:
                query += " AND d.destination_type = ?"
                params.append(destination_type)
            if contact_made is not None:
                query += " AND d.contact_made = ?"
                params.append(contact_made)
            query += " ORDER BY s.last_name"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_destination(self, dest_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"destination_type", "institution_name", "course_title",
                        "contact_made", "notes"}
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{validate_identifier(k)} = ?")
                    params.append(v)
            if not parts:
                raise ComplianceError("No valid fields to update")
            params.append(dest_id)
            conn.execute(f"UPDATE destinations SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            row = conn.execute("SELECT * FROM destinations WHERE id = ?", (dest_id,)).fetchone()
            return dict(row) if row else {}
        except ComplianceError:
            raise
        except Exception as e:
            raise ComplianceError(f"Failed to update destination: {e}")
        finally:
            conn.close()
