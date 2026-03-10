"""Intervention groups service."""

import logging
from education_system.secondary_school.core.exceptions import InterventionError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class InterventionService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_group(self, name, subject_id=None, year_group=None, lead_teacher=None,
                     target=None, start_date=None, end_date=None, meeting_frequency=None, notes=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO intervention_groups
                   (name, subject_id, year_group, lead_teacher, target,
                    start_date, end_date, meeting_frequency, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, subject_id, year_group, lead_teacher, target,
                 start_date, end_date, meeting_frequency, notes))
            conn.commit()
            return dict(conn.execute("SELECT * FROM intervention_groups WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise InterventionError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_groups(self, status="active"):
        conn = self._conn()
        try:
            sql = """SELECT ig.*, sub.title as subject_title
                     FROM intervention_groups ig
                     LEFT JOIN subjects sub ON ig.subject_id = sub.id
                     WHERE 1=1"""
            params = []
            if status:
                sql += " AND ig.status = ?"
                params.append(status)
            sql += " ORDER BY ig.name"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def close_group(self, group_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE intervention_groups SET status = 'closed' WHERE id = ?", (group_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_group(self, group_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM intervention_members WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM intervention_groups WHERE id = ?", (group_id,))
            conn.commit()
        finally:
            conn.close()

    # --- Members ---

    def add_member(self, group_id, student_id, baseline_grade=None, target_grade=None):
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO intervention_members (group_id, student_id, baseline_grade, target_grade)
                   VALUES (?, ?, ?, ?)""",
                (group_id, student_id, baseline_grade, target_grade))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise InterventionError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_members(self, group_id):
        conn = self._conn()
        try:
            sql = """SELECT im.*, s.first_name, s.last_name, s.student_id as stu_code, s.year_group
                     FROM intervention_members im
                     JOIN students s ON im.student_id = s.id
                     WHERE im.group_id = ?
                     ORDER BY s.last_name"""
            return [dict(r) for r in conn.execute(sql, (group_id,)).fetchall()]
        finally:
            conn.close()

    def update_member_progress(self, member_id, current_grade=None, progress_notes=None):
        conn = self._conn()
        try:
            updates = []
            params = []
            if current_grade is not None:
                updates.append("current_grade = ?")
                params.append(current_grade)
            if progress_notes is not None:
                updates.append("progress_notes = ?")
                params.append(progress_notes)
            if updates:
                params.append(member_id)
                conn.execute(f"UPDATE intervention_members SET {', '.join(updates)} WHERE id = ?", params)
                conn.commit()
        finally:
            conn.close()

    def remove_member(self, member_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM intervention_members WHERE id = ?", (member_id,))
            conn.commit()
        finally:
            conn.close()
