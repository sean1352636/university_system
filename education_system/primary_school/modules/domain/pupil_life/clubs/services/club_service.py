"""Club management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import ClubsError
from education_system.primary_school.core.sql_safety import validate_identifier
import traceback

logger = logging.getLogger(__name__)


class ClubService:
    """CRUD operations for clubs and memberships."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_club(self, club_name, day_of_week=None, start_time=None,
                    end_time=None, location=None, staff_id=None,
                    max_capacity=None, year_groups=None, term=None,
                    description=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO clubs (
                    club_name, day_of_week, start_time, end_time, location,
                    staff_id, max_capacity, year_groups, term, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    club_name, day_of_week, start_time, end_time, location,
                    staff_id, max_capacity, year_groups, term, description,
                ),
            )
            conn.commit()
            club_id = cursor.lastrowid
            logger.info("Created club: %s (id=%s)", club_name, club_id)
            return {"id": club_id, "club_name": club_name}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ClubsError(f"Failed to create club: {e}") from e
        finally:
            conn.close()

    def get_club(self, club_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clubs WHERE id = ?", (club_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_clubs(self, status="Active", day_of_week=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM clubs WHERE 1=1"
            params = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if day_of_week:
                sql += " AND day_of_week = ?"
                params.append(day_of_week)
            sql += " ORDER BY club_name"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_club(self, club_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "club_name", "day_of_week", "start_time", "end_time",
                "location", "staff_id", "max_capacity", "year_groups",
                "term", "description", "status",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(club_id)
            cursor.execute(
                f"UPDATE clubs SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated club id=%s", club_id)
            return self.get_club(club_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ClubsError(f"Failed to update club: {e}") from e
        finally:
            conn.close()

    def delete_club(self, club_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM club_members WHERE club_id = ?", (club_id,))
            cursor.execute("DELETE FROM clubs WHERE id = ?", (club_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted club id=%s", club_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ClubsError(f"Failed to delete club: {e}") from e
        finally:
            conn.close()

    def add_member(self, club_id, pupil_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO club_members (club_id, pupil_id) VALUES (?, ?)",
                (club_id, pupil_id),
            )
            conn.commit()
            logger.info("Added pupil %s to club id=%s", pupil_id, club_id)
            return True
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ClubsError(f"Failed to add club member: {e}") from e
        finally:
            conn.close()

    def remove_member(self, club_id, pupil_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM club_members WHERE club_id = ? AND pupil_id = ?",
                (club_id, pupil_id),
            )
            removed = cursor.rowcount > 0
            conn.commit()
            if removed:
                logger.info("Removed pupil %s from club id=%s", pupil_id, club_id)
            return removed
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ClubsError(f"Failed to remove club member: {e}") from e
        finally:
            conn.close()

    def get_members(self, club_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT p.* FROM pupils p
                JOIN club_members cm ON p.pupil_id = cm.pupil_id
                WHERE cm.club_id = ?
                ORDER BY p.last_name, p.first_name""",
                (club_id,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_pupil_clubs(self, pupil_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT c.* FROM clubs c
                JOIN club_members cm ON c.id = cm.club_id
                WHERE cm.pupil_id = ?
                ORDER BY c.club_name""",
                (pupil_id,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
