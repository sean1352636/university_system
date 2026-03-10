"""Department and group management service."""

from education_system.college_system.core.exceptions import DepartmentError, GroupError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class DepartmentService:
    """Service for managing departments and faculties."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_department(self, code: str, name: str, faculty: str | None = None,
                          head_of_department: int | None = None,
                          curriculum_area: str | None = None,
                          description: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO departments (code, name, faculty, head_of_department,
                   curriculum_area, description)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (code, name, faculty, head_of_department, curriculum_area, description),
            )
            conn.commit()
            logger.info("Department created: code=%s name=%s", code, name)
            row = conn.execute(
                "SELECT * FROM departments WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except DepartmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise DepartmentError(f"Failed to create department: {e}") from e
        finally:
            conn.close()

    def get_department(self, dept_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM departments WHERE id = ?", (dept_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_departments(self, status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM departments WHERE status = ? ORDER BY name", (status,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM departments ORDER BY name").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_department(self, dept_id: int, **updates) -> dict:
        allowed = {"code", "name", "faculty", "head_of_department", "curriculum_area", "description", "status"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise DepartmentError("No valid fields to update.")
        updates["updated_at"] = "datetime('now')"

        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM departments WHERE id = ?", (dept_id,)).fetchone()
            if not existing:
                raise DepartmentError("Department not found.")

            set_parts = []
            values = []
            for k, v in updates.items():
                if k == "updated_at":
                    set_parts.append("updated_at = datetime('now')")
                else:
                    set_parts.append(f"{k} = ?")
                    values.append(v)
            values.append(dept_id)

            conn.execute(
                f"UPDATE departments SET {', '.join(set_parts)} WHERE id = ?", values
            )
            conn.commit()
            logger.info("Department updated: id=%d", dept_id)
            row = conn.execute("SELECT * FROM departments WHERE id = ?", (dept_id,)).fetchone()
            return dict(row)
        except DepartmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise DepartmentError(f"Failed to update department: {e}") from e
        finally:
            conn.close()

    def delete_department(self, dept_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM departments WHERE id = ?", (dept_id,)).fetchone()
            if not existing:
                raise DepartmentError("Department not found.")
            conn.execute(
                "UPDATE departments SET status = 'inactive', updated_at = datetime('now') WHERE id = ?",
                (dept_id,),
            )
            conn.commit()
            logger.info("Department soft-deleted: id=%d", dept_id)
            return True
        except DepartmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise DepartmentError(f"Failed to delete department: {e}") from e
        finally:
            conn.close()

    def get_department_courses(self, dept_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT c.* FROM courses c
                   WHERE c.subject_area = (SELECT curriculum_area FROM departments WHERE id = ?)
                   ORDER BY c.course_code""",
                (dept_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_department_staff(self, dept_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT s.* FROM staff s
                   WHERE s.department = (SELECT name FROM departments WHERE id = ?)
                   ORDER BY s.last_name""",
                (dept_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


class GroupService:
    """Service for managing tutor groups, teaching groups, and memberships."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # -- Tutor Groups --

    def create_tutor_group(self, name: str, year_group: str | None = None,
                           tutor_id: int | None = None, room_id: int | None = None,
                           max_size: int = 30) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO tutor_groups (name, year_group, tutor_id, room_id, max_size)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, year_group, tutor_id, room_id, max_size),
            )
            conn.commit()
            logger.info("Tutor group created: name=%s", name)
            row = conn.execute("SELECT * FROM tutor_groups WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise GroupError(f"Failed to create tutor group: {e}") from e
        finally:
            conn.close()

    def list_tutor_groups(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute("SELECT * FROM tutor_groups ORDER BY name").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_tutor_group(self, group_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM tutor_groups WHERE id = ?", (group_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_tutor_group(self, group_id: int, **updates) -> dict:
        allowed = {"name", "year_group", "tutor_id", "room_id", "max_size"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise GroupError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM tutor_groups WHERE id = ?", (group_id,)).fetchone()
            if not existing:
                raise GroupError("Tutor group not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE tutor_groups SET {set_parts} WHERE id = ?",
                         (*updates.values(), group_id))
            conn.commit()
            logger.info("Tutor group updated: id=%d", group_id)
            row = conn.execute("SELECT * FROM tutor_groups WHERE id = ?", (group_id,)).fetchone()
            return dict(row)
        except GroupError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise GroupError(f"Failed to update tutor group: {e}") from e
        finally:
            conn.close()

    def delete_tutor_group(self, group_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM tutor_groups WHERE id = ?", (group_id,)).fetchone()
            if not existing:
                raise GroupError("Tutor group not found.")
            conn.execute("DELETE FROM tutor_groups WHERE id = ?", (group_id,))
            conn.commit()
            logger.info("Tutor group deleted: id=%d", group_id)
            return True
        except GroupError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise GroupError(f"Failed to delete tutor group: {e}") from e
        finally:
            conn.close()

    # -- Teaching Groups --

    def create_teaching_group(self, name: str, course_id: int,
                              academic_year: str | None = None,
                              max_size: int = 30) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO teaching_groups (name, course_id, academic_year, max_size)
                   VALUES (?, ?, ?, ?)""",
                (name, course_id, academic_year, max_size),
            )
            conn.commit()
            logger.info("Teaching group created: name=%s course=%d", name, course_id)
            row = conn.execute("SELECT * FROM teaching_groups WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise GroupError(f"Failed to create teaching group: {e}") from e
        finally:
            conn.close()

    def list_teaching_groups(self, course_id: int | None = None) -> list[dict]:
        conn = self._conn()
        try:
            if course_id:
                rows = conn.execute(
                    "SELECT * FROM teaching_groups WHERE course_id = ? ORDER BY name",
                    (course_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM teaching_groups ORDER BY name").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_teaching_group(self, group_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM teaching_groups WHERE id = ?", (group_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_teaching_group(self, group_id: int, **updates) -> dict:
        allowed = {"name", "course_id", "academic_year", "max_size"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise GroupError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM teaching_groups WHERE id = ?", (group_id,)).fetchone()
            if not existing:
                raise GroupError("Teaching group not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE teaching_groups SET {set_parts} WHERE id = ?",
                         (*updates.values(), group_id))
            conn.commit()
            logger.info("Teaching group updated: id=%d", group_id)
            row = conn.execute("SELECT * FROM teaching_groups WHERE id = ?", (group_id,)).fetchone()
            return dict(row)
        except GroupError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise GroupError(f"Failed to update teaching group: {e}") from e
        finally:
            conn.close()

    def delete_teaching_group(self, group_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM teaching_groups WHERE id = ?", (group_id,)).fetchone()
            if not existing:
                raise GroupError("Teaching group not found.")
            conn.execute("DELETE FROM teaching_groups WHERE id = ?", (group_id,))
            conn.commit()
            logger.info("Teaching group deleted: id=%d", group_id)
            return True
        except GroupError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise GroupError(f"Failed to delete teaching group: {e}") from e
        finally:
            conn.close()

    # -- Members --

    def add_member(self, group_id: int, group_type: str, student_id: int) -> dict:
        if group_type not in ("tutor", "teaching"):
            raise GroupError("group_type must be 'tutor' or 'teaching'.")
        conn = self._conn()
        try:
            existing = conn.execute(
                """SELECT id FROM group_members
                   WHERE group_id = ? AND group_type = ? AND student_id = ? AND left_date IS NULL""",
                (group_id, group_type, student_id),
            ).fetchone()
            if existing:
                raise GroupError("Student is already a member of this group.")
            conn.execute(
                """INSERT INTO group_members (group_id, group_type, student_id)
                   VALUES (?, ?, ?)""",
                (group_id, group_type, student_id),
            )
            conn.commit()
            logger.info("Member added: group=%d type=%s student=%d", group_id, group_type, student_id)
            row = conn.execute("SELECT * FROM group_members WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except GroupError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise GroupError(f"Failed to add member: {e}") from e
        finally:
            conn.close()

    def remove_member(self, member_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM group_members WHERE id = ?", (member_id,)).fetchone()
            if not existing:
                raise GroupError("Membership not found.")
            conn.execute(
                "UPDATE group_members SET left_date = date('now') WHERE id = ?",
                (member_id,),
            )
            conn.commit()
            logger.info("Member removed: id=%d", member_id)
            return True
        except GroupError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise GroupError(f"Failed to remove member: {e}") from e
        finally:
            conn.close()

    def list_members(self, group_id: int, group_type: str,
                     active_only: bool = True) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT gm.*, s.student_id as sid, s.first_name, s.last_name
                     FROM group_members gm
                     JOIN students s ON gm.student_id = s.id
                     WHERE gm.group_id = ? AND gm.group_type = ?"""
            params: list = [group_id, group_type]
            if active_only:
                sql += " AND gm.left_date IS NULL"
            sql += " ORDER BY s.last_name, s.first_name"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_student_groups(self, student_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT gm.*,
                   CASE gm.group_type
                     WHEN 'tutor' THEN tg.name
                     WHEN 'teaching' THEN teg.name
                   END as group_name
                   FROM group_members gm
                   LEFT JOIN tutor_groups tg ON gm.group_id = tg.id AND gm.group_type = 'tutor'
                   LEFT JOIN teaching_groups teg ON gm.group_id = teg.id AND gm.group_type = 'teaching'
                   WHERE gm.student_id = ? AND gm.left_date IS NULL
                   ORDER BY gm.group_type, gm.joined_date""",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
