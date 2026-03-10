"""Governance & Board service."""

from education_system.college_system.core.exceptions import GovernanceError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class GovernanceService:
    """Governance & Board service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def add_governor(self, first_name: str, last_name: str, governor_type: str = "community",
                     email: str | None = None, phone: str | None = None,
                     role_on_board: str | None = None, appointed_date: str | None = None,
                     term_end_date: str | None = None, skills: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO governors (first_name, last_name, governor_type, email, phone,
                   role_on_board, appointed_date, term_end_date, skills)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (first_name, last_name, governor_type, email, phone,
                 role_on_board, appointed_date, term_end_date, skills),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM governors WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise GovernanceError(f"Failed to add governor: {e}") from e
        finally:
            conn.close()

    def list_governors(self, status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM governors WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY last_name, first_name"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def update_governor(self, governor_id: int, **updates) -> dict:
        allowed = {"email", "phone", "role_on_board", "term_end_date", "dbs_checked", "dbs_date", "skills", "status"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [governor_id]
            conn.execute(f"UPDATE governors SET {sets} WHERE id = ?", vals)
            conn.commit()
            row = conn.execute("SELECT * FROM governors WHERE id = ?", (governor_id,)).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise GovernanceError(f"Failed to update governor: {e}") from e
        finally:
            conn.close()

    def create_meeting(self, meeting_date: str, meeting_type: str = "full_board",
                       location: str | None = None, chair_id: int | None = None,
                       agenda: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO board_meetings (meeting_date, meeting_type, location, chair_id, agenda) VALUES (?, ?, ?, ?, ?)",
                (meeting_date, meeting_type, location, chair_id, agenda),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM board_meetings WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise GovernanceError(f"Failed to create meeting: {e}") from e
        finally:
            conn.close()

    def list_meetings(self, status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM board_meetings WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY meeting_date DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def add_action(self, meeting_id: int, action_description: str,
                   assigned_to: int | None = None, due_date: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO board_actions (meeting_id, action_description, assigned_to, due_date) VALUES (?, ?, ?, ?)",
                (meeting_id, action_description, assigned_to, due_date),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM board_actions WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise GovernanceError(f"Failed to add action: {e}") from e
        finally:
            conn.close()

    def list_actions(self, meeting_id: int | None = None, status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM board_actions WHERE 1=1"
            params: list = []
            if meeting_id:
                sql += " AND meeting_id = ?"
                params.append(meeting_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY due_date"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def add_strategic_plan(self, title: str, priority_area: str | None = None,
                           objective: str | None = None, success_measure: str | None = None,
                           responsible_person: str | None = None, academic_year: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO strategic_plans (title, academic_year, priority_area, objective, success_measure, responsible_person)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (title, academic_year, priority_area, objective, success_measure, responsible_person),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM strategic_plans WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise GovernanceError(f"Failed to add plan: {e}") from e
        finally:
            conn.close()

    def list_strategic_plans(self, status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM strategic_plans WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

