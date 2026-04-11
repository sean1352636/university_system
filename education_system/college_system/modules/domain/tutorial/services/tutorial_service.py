"""Tutorial System service layer."""

from education_system.college_system.core.exceptions import TutorialError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class TutorialService:
    """Service for managing tutor assignments, tutorial sessions, and 1-to-1 records."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        conn = connect(self._db_path)
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        return conn

    # ── Tutor Assignments ──────────────────────────────────────────────

    def list_assignments(self, tutor_id: int | None = None,
                         tutor_group: str | None = None,
                         status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT ta.*, s.first_name AS student_first, s.last_name AS student_last,
                            st.first_name AS tutor_first, st.last_name AS tutor_last
                     FROM tutor_assignments ta
                     LEFT JOIN students s ON ta.student_id = s.id
                     LEFT JOIN staff st ON ta.tutor_id = st.id
                     WHERE 1=1"""
            params: list = []
            if tutor_id is not None:
                sql += " AND ta.tutor_id = ?"
                params.append(tutor_id)
            if tutor_group is not None:
                sql += " AND ta.tutor_group = ?"
                params.append(tutor_group)
            if status is not None:
                sql += " AND ta.status = ?"
                params.append(status)
            sql += " ORDER BY ta.created_at DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_assignment(self, assignment_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT ta.*, s.first_name AS student_first, s.last_name AS student_last,
                          st.first_name AS tutor_first, st.last_name AS tutor_last
                   FROM tutor_assignments ta
                   LEFT JOIN students s ON ta.student_id = s.id
                   LEFT JOIN staff st ON ta.tutor_id = st.id
                   WHERE ta.id = ?""",
                (assignment_id,),
            ).fetchone()
            return row
        finally:
            conn.close()

    def create_assignment(self, student_id: int, tutor_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            fields = {"student_id": student_id, "tutor_id": tutor_id}
            for key in ("academic_year", "tutor_group", "status"):
                if key in kwargs and kwargs[key] is not None:
                    fields[key] = kwargs[key]
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO tutor_assignments ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            logger.info("Tutor assignment created: student=%d tutor=%d", student_id, tutor_id)
            row = conn.execute(
                "SELECT * FROM tutor_assignments WHERE id = last_insert_rowid()"
            ).fetchone()
            return row
        except Exception as e:
            conn.rollback()
            raise TutorialError(f"Failed to create assignment: {e}") from e
        finally:
            conn.close()

    def update_assignment(self, assignment_id: int, **updates) -> dict:
        set_parts: list[str] = []
        values: list = []
        for col in ("academic_year", "status", "student_id", "tutor_group", "tutor_id"):
            if col in updates and updates[col] is not None:
                set_parts.append(f"{col} = ?")
                values.append(updates[col])
        if not set_parts:
            raise TutorialError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM tutor_assignments WHERE id = ?", (assignment_id,)
            ).fetchone()
            if not existing:
                raise TutorialError("Assignment not found.")
            set_clause = ", ".join(set_parts)
            values.append(assignment_id)
            conn.execute(
                f"UPDATE tutor_assignments SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Assignment updated: id=%d", assignment_id)
            return conn.execute(
                "SELECT * FROM tutor_assignments WHERE id = ?", (assignment_id,)
            ).fetchone()
        except TutorialError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise TutorialError(f"Failed to update assignment: {e}") from e
        finally:
            conn.close()

    def delete_assignment(self, assignment_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM tutor_assignments WHERE id = ?", (assignment_id,)
            ).fetchone()
            if not existing:
                raise TutorialError("Assignment not found.")
            conn.execute("DELETE FROM tutor_assignments WHERE id = ?", (assignment_id,))
            conn.commit()
            logger.info("Assignment deleted: id=%d", assignment_id)
            return True
        except TutorialError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise TutorialError(f"Failed to delete assignment: {e}") from e
        finally:
            conn.close()

    def end_assignment(self, assignment_id: int) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM tutor_assignments WHERE id = ?", (assignment_id,)
            ).fetchone()
            if not existing:
                raise TutorialError("Assignment not found.")
            conn.execute(
                "UPDATE tutor_assignments SET status = 'ended' WHERE id = ?",
                (assignment_id,),
            )
            conn.commit()
            logger.info("Assignment ended: id=%d", assignment_id)
            return conn.execute(
                "SELECT * FROM tutor_assignments WHERE id = ?", (assignment_id,)
            ).fetchone()
        except TutorialError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise TutorialError(f"Failed to end assignment: {e}") from e
        finally:
            conn.close()

    def get_tutor_group(self, tutor_group: str) -> list[dict]:
        """Return all students assigned to a tutor group."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT ta.*, s.first_name AS student_first, s.last_name AS student_last,
                          s.student_id AS student_ref
                   FROM tutor_assignments ta
                   LEFT JOIN students s ON ta.student_id = s.id
                   WHERE ta.tutor_group = ? AND ta.status = 'active'
                   ORDER BY s.last_name, s.first_name""",
                (tutor_group,),
            ).fetchall()
            return rows
        finally:
            conn.close()

    # ── Tutorial Sessions ──────────────────────────────────────────────

    def list_sessions(self, tutor_id: int | None = None,
                      tutor_group: str | None = None,
                      status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT ts.*, st.first_name AS tutor_first, st.last_name AS tutor_last
                     FROM tutorial_sessions ts
                     LEFT JOIN staff st ON ts.tutor_id = st.id
                     WHERE 1=1"""
            params: list = []
            if tutor_id is not None:
                sql += " AND ts.tutor_id = ?"
                params.append(tutor_id)
            if tutor_group is not None:
                sql += " AND ts.tutor_group = ?"
                params.append(tutor_group)
            if status is not None:
                sql += " AND ts.status = ?"
                params.append(status)
            sql += " ORDER BY ts.session_date DESC, ts.created_at DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_session(self, session_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT ts.*, st.first_name AS tutor_first, st.last_name AS tutor_last
                   FROM tutorial_sessions ts
                   LEFT JOIN staff st ON ts.tutor_id = st.id
                   WHERE ts.id = ?""",
                (session_id,),
            ).fetchone()
            return row
        finally:
            conn.close()

    def create_session(self, tutor_id: int, session_date: str, **kwargs) -> dict:
        conn = self._conn()
        try:
            fields = {"tutor_id": tutor_id, "session_date": session_date}
            for key in ("tutor_group", "session_type", "topic", "resources", "notes", "status"):
                if key in kwargs and kwargs[key] is not None:
                    fields[key] = kwargs[key]
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO tutorial_sessions ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            logger.info("Session created: tutor=%d date=%s", tutor_id, session_date)
            row = conn.execute(
                "SELECT * FROM tutorial_sessions WHERE id = last_insert_rowid()"
            ).fetchone()
            return row
        except Exception as e:
            conn.rollback()
            raise TutorialError(f"Failed to create session: {e}") from e
        finally:
            conn.close()

    def update_session(self, session_id: int, **updates) -> dict:
        allowed = {"tutor_id", "tutor_group", "session_date", "session_type",
                    "topic", "resources", "notes", "status"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise TutorialError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM tutorial_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not existing:
                raise TutorialError("Session not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE tutorial_sessions SET {set_parts} WHERE id = ?",
                (*updates.values(), session_id),
            )
            conn.commit()
            logger.info("Session updated: id=%d", session_id)
            return conn.execute(
                "SELECT * FROM tutorial_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        except TutorialError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise TutorialError(f"Failed to update session: {e}") from e
        finally:
            conn.close()

    def delete_session(self, session_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM tutorial_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not existing:
                raise TutorialError("Session not found.")
            conn.execute("DELETE FROM tutorial_sessions WHERE id = ?", (session_id,))
            conn.commit()
            logger.info("Session deleted: id=%d", session_id)
            return True
        except TutorialError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise TutorialError(f"Failed to delete session: {e}") from e
        finally:
            conn.close()

    def complete_session(self, session_id: int, notes: str | None = None) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM tutorial_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not existing:
                raise TutorialError("Session not found.")
            if notes:
                conn.execute(
                    "UPDATE tutorial_sessions SET status = 'completed', notes = ? WHERE id = ?",
                    (notes, session_id),
                )
            else:
                conn.execute(
                    "UPDATE tutorial_sessions SET status = 'completed' WHERE id = ?",
                    (session_id,),
                )
            conn.commit()
            logger.info("Session completed: id=%d", session_id)
            return conn.execute(
                "SELECT * FROM tutorial_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        except TutorialError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise TutorialError(f"Failed to complete session: {e}") from e
        finally:
            conn.close()

    # ── Tutorial Records (1-to-1 meetings) ─────────────────────────────

    def list_records(self, student_id: int | None = None,
                     tutor_id: int | None = None,
                     meeting_type: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT tr.*, s.first_name AS student_first, s.last_name AS student_last,
                            st.first_name AS tutor_first, st.last_name AS tutor_last
                     FROM tutorial_records tr
                     LEFT JOIN students s ON tr.student_id = s.id
                     LEFT JOIN staff st ON tr.tutor_id = st.id
                     WHERE 1=1"""
            params: list = []
            if student_id is not None:
                sql += " AND tr.student_id = ?"
                params.append(student_id)
            if tutor_id is not None:
                sql += " AND tr.tutor_id = ?"
                params.append(tutor_id)
            if meeting_type is not None:
                sql += " AND tr.meeting_type = ?"
                params.append(meeting_type)
            sql += " ORDER BY tr.meeting_date DESC, tr.created_at DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_record(self, record_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT tr.*, s.first_name AS student_first, s.last_name AS student_last,
                          st.first_name AS tutor_first, st.last_name AS tutor_last
                   FROM tutorial_records tr
                   LEFT JOIN students s ON tr.student_id = s.id
                   LEFT JOIN staff st ON tr.tutor_id = st.id
                   WHERE tr.id = ?""",
                (record_id,),
            ).fetchone()
            return row
        finally:
            conn.close()

    def create_record(self, student_id: int, tutor_id: int,
                      meeting_date: str, **kwargs) -> dict:
        conn = self._conn()
        try:
            fields = {
                "student_id": student_id,
                "tutor_id": tutor_id,
                "meeting_date": meeting_date,
            }
            for key in ("session_id", "meeting_type", "discussion_notes",
                         "targets_set", "student_concerns", "follow_up_required",
                         "follow_up_notes"):
                if key in kwargs and kwargs[key] is not None:
                    fields[key] = kwargs[key]
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO tutorial_records ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            logger.info("Record created: student=%d tutor=%d date=%s",
                        student_id, tutor_id, meeting_date)
            row = conn.execute(
                "SELECT * FROM tutorial_records WHERE id = last_insert_rowid()"
            ).fetchone()
            return row
        except Exception as e:
            conn.rollback()
            raise TutorialError(f"Failed to create record: {e}") from e
        finally:
            conn.close()

    def update_record(self, record_id: int, **updates) -> dict:
        allowed = {"session_id", "student_id", "tutor_id", "meeting_date",
                    "meeting_type", "discussion_notes", "targets_set",
                    "student_concerns", "follow_up_required", "follow_up_notes"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise TutorialError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM tutorial_records WHERE id = ?", (record_id,)
            ).fetchone()
            if not existing:
                raise TutorialError("Record not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE tutorial_records SET {set_parts} WHERE id = ?",
                (*updates.values(), record_id),
            )
            conn.commit()
            logger.info("Record updated: id=%d", record_id)
            return conn.execute(
                "SELECT * FROM tutorial_records WHERE id = ?", (record_id,)
            ).fetchone()
        except TutorialError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise TutorialError(f"Failed to update record: {e}") from e
        finally:
            conn.close()

    def delete_record(self, record_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM tutorial_records WHERE id = ?", (record_id,)
            ).fetchone()
            if not existing:
                raise TutorialError("Record not found.")
            conn.execute("DELETE FROM tutorial_records WHERE id = ?", (record_id,))
            conn.commit()
            logger.info("Record deleted: id=%d", record_id)
            return True
        except TutorialError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise TutorialError(f"Failed to delete record: {e}") from e
        finally:
            conn.close()

    def get_follow_ups(self, tutor_id: int | None = None) -> list[dict]:
        """Return all records where follow-up is required."""
        conn = self._conn()
        try:
            sql = """SELECT tr.*, s.first_name AS student_first, s.last_name AS student_last,
                            st.first_name AS tutor_first, st.last_name AS tutor_last
                     FROM tutorial_records tr
                     LEFT JOIN students s ON tr.student_id = s.id
                     LEFT JOIN staff st ON tr.tutor_id = st.id
                     WHERE tr.follow_up_required = 1"""
            params: list = []
            if tutor_id is not None:
                sql += " AND tr.tutor_id = ?"
                params.append(tutor_id)
            sql += " ORDER BY tr.meeting_date DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    # ── Statistics ─────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            # Assignments
            total_assignments = conn.execute(
                "SELECT COUNT(*) AS cnt FROM tutor_assignments"
            ).fetchone()["cnt"]
            active_assignments = conn.execute(
                "SELECT COUNT(*) AS cnt FROM tutor_assignments WHERE status = 'active'"
            ).fetchone()["cnt"]

            # Tutor groups count
            tutor_groups_count = conn.execute(
                "SELECT COUNT(DISTINCT tutor_group) AS cnt FROM tutor_assignments WHERE tutor_group IS NOT NULL"
            ).fetchone()["cnt"]

            # Sessions
            total_sessions = conn.execute(
                "SELECT COUNT(*) AS cnt FROM tutorial_sessions"
            ).fetchone()["cnt"]
            completed_sessions = conn.execute(
                "SELECT COUNT(*) AS cnt FROM tutorial_sessions WHERE status = 'completed'"
            ).fetchone()["cnt"]
            session_type_rows = conn.execute(
                "SELECT session_type, COUNT(*) AS cnt FROM tutorial_sessions GROUP BY session_type"
            ).fetchall()
            by_session_type = {r["session_type"]: r["cnt"] for r in session_type_rows}

            # Records
            total_records = conn.execute(
                "SELECT COUNT(*) AS cnt FROM tutorial_records"
            ).fetchone()["cnt"]
            meeting_type_rows = conn.execute(
                "SELECT meeting_type, COUNT(*) AS cnt FROM tutorial_records GROUP BY meeting_type"
            ).fetchall()
            by_meeting_type = {r["meeting_type"]: r["cnt"] for r in meeting_type_rows}
            follow_ups_pending = conn.execute(
                "SELECT COUNT(*) AS cnt FROM tutorial_records WHERE follow_up_required = 1"
            ).fetchone()["cnt"]

            return {
                "total_assignments": total_assignments,
                "active_assignments": active_assignments,
                "tutor_groups_count": tutor_groups_count,
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
                "by_session_type": by_session_type,
                "total_records": total_records,
                "by_meeting_type": by_meeting_type,
                "follow_ups_pending": follow_ups_pending,
            }
        finally:
            conn.close()
