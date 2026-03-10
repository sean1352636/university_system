"""Visitor service for the Primary School Management System."""

import logging
from datetime import date

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import VisitorError
import traceback

logger = logging.getLogger(__name__)


class VisitorService:
    """CRUD operations for visitor sign-in/sign-out."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def sign_in(self, visitor_name, purpose, visiting=None,
                organisation=None, dbs_checked=0,
                safeguarding_briefing=0, badge_number=None):
        """Sign in a visitor."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO visitors (
                    visitor_name, purpose, visiting, organisation,
                    dbs_checked, safeguarding_briefing, badge_number,
                    visit_date, sign_in_time, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, date('now'),
                          time('now'), datetime('now'))""",
                (visitor_name, purpose, visiting, organisation,
                 dbs_checked, safeguarding_briefing, badge_number),
            )
            conn.commit()
            visitor_id = cursor.lastrowid
            logger.info("Visitor signed in: %s (id=%s), purpose: %s",
                        visitor_name, visitor_id, purpose)
            return {"id": visitor_id, "visitor_name": visitor_name,
                    "status": "Signed In"}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise VisitorError(f"Failed to sign in visitor: {e}") from e
        finally:
            conn.close()

    def sign_out(self, visitor_id):
        """Sign out a visitor."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE visitors
                   SET sign_out_time = time('now'),
                       updated_at = datetime('now')
                   WHERE id = ? AND sign_out_time IS NULL""",
                (visitor_id,),
            )
            conn.commit()
            if cursor.rowcount == 0:
                raise VisitorError(
                    f"Visitor {visitor_id} is not currently signed in")
            logger.info("Visitor signed out: id=%s", visitor_id)
            return True
        except VisitorError:
            raise
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise VisitorError(f"Failed to sign out visitor: {e}") from e
        finally:
            conn.close()

    def get_visitor(self, visitor_id):
        """Get a single visitor record by ID."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM visitors WHERE id = ?", (visitor_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_visitors(self, date=None, signed_out=None):
        """List visitors with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM visitors WHERE 1=1"
            params = []
            if date:
                sql += " AND visit_date = ?"
                params.append(date)
            if signed_out is not None:
                if signed_out:
                    sql += " AND sign_out_time IS NOT NULL"
                else:
                    sql += " AND sign_out_time IS NULL"
            sql += " ORDER BY visit_date DESC, sign_in_time DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_current_visitors(self):
        """Get all visitors currently signed in (today, not yet signed out)."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            today = date.today().isoformat()
            cursor.execute(
                """SELECT * FROM visitors
                   WHERE sign_out_time IS NULL
                     AND visit_date = ?
                   ORDER BY sign_in_time""",
                (today,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
