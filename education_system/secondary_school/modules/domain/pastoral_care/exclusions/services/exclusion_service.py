"""Exclusion tracking service."""

import logging
from education_system.secondary_school.core.exceptions import ExclusionError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

EXCLUSION_TYPES = ("fixed_term", "permanent", "lunchtime", "internal")
EXCLUSION_CATEGORIES = ("persistent_disruptive", "physical_assault_pupil", "physical_assault_adult",
                        "verbal_abuse_pupil", "verbal_abuse_adult", "bullying", "drugs_alcohol",
                        "damage", "theft", "sexual_misconduct", "racist_abuse", "other")


class ExclusionService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_exclusion(self, student_id, reason, exclusion_type="fixed_term",
                         category="persistent_disruptive", start_date=None, end_date=None,
                         days=1, excluded_by=None, alternative_provision=None, notes=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO exclusions
                   (student_id, exclusion_type, reason, category, start_date, end_date,
                    days, excluded_by, alternative_provision, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, exclusion_type, reason, category, start_date, end_date,
                 days, excluded_by, alternative_provision, notes))
            conn.commit()
            return dict(conn.execute("SELECT * FROM exclusions WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise ExclusionError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_exclusions(self, student_id=None, exclusion_type=None, status="active"):
        conn = self._conn()
        try:
            sql = """SELECT e.*, s.first_name, s.last_name, s.student_id AS stu_code, s.year_group
                     FROM exclusions e JOIN students s ON e.student_id = s.id WHERE 1=1"""
            params = []
            if student_id:
                sql += " AND e.student_id = ?"
                params.append(student_id)
            if exclusion_type:
                sql += " AND e.exclusion_type = ?"
                params.append(exclusion_type)
            if status:
                sql += " AND e.status = ?"
                params.append(status)
            sql += " ORDER BY e.start_date DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def update_notifications(self, exclusion_id, parent_notified=None, la_notified=None):
        conn = self._conn()
        try:
            if parent_notified is not None:
                conn.execute("UPDATE exclusions SET parent_notified = ? WHERE id = ?",
                             (int(parent_notified), exclusion_id))
            if la_notified is not None:
                conn.execute("UPDATE exclusions SET la_notified = ? WHERE id = ?",
                             (int(la_notified), exclusion_id))
            conn.commit()
        finally:
            conn.close()

    def update_governor_review(self, exclusion_id, review_date):
        conn = self._conn()
        try:
            conn.execute("UPDATE exclusions SET governor_review = 1, governor_review_date = ? WHERE id = ?",
                         (review_date, exclusion_id))
            conn.commit()
        finally:
            conn.close()

    def update_reintegration(self, exclusion_id, reintegration_date):
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE exclusions SET reintegration_meeting = 1, reintegration_date = ? WHERE id = ?",
                (reintegration_date, exclusion_id))
            conn.commit()
        finally:
            conn.close()

    def close_exclusion(self, exclusion_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE exclusions SET status = 'closed' WHERE id = ?", (exclusion_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_exclusion(self, exclusion_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM exclusions WHERE id = ?", (exclusion_id,))
            conn.commit()
        finally:
            conn.close()

    def summary(self):
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT exclusion_type, COUNT(*) as cnt, SUM(days) as total_days
                   FROM exclusions WHERE status = 'active'
                   GROUP BY exclusion_type ORDER BY cnt DESC"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
