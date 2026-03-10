"""Permissions & Consent service."""

import logging
from education_system.secondary_school.core.exceptions import ConsentError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

CONSENT_TYPES = ("photo_internal", "photo_external", "photo_social_media", "photo_press",
                 "medical_treatment", "trip_blanket", "data_sharing", "biometric",
                 "online_platforms", "contact_by_email", "contact_by_sms")


class ConsentService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def add_record(self, student_id, consent_type, granted=False, granted_by=None,
                   granted_date=None, expires_at=None, description=None,
                   academic_year="2025/2026"):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO consent_records
                   (student_id, consent_type, description, granted, granted_by,
                    granted_date, expires_at, academic_year)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, consent_type, description, int(granted), granted_by,
                 granted_date, expires_at, academic_year))
            conn.commit()
            return dict(conn.execute("SELECT * FROM consent_records WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise ConsentError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_records(self, student_id=None, consent_type=None, granted_only=False):
        conn = self._conn()
        try:
            sql = """SELECT cr.*, s.first_name, s.last_name, s.student_id AS stu_code, s.year_group
                     FROM consent_records cr JOIN students s ON cr.student_id = s.id
                     WHERE cr.status = 'active'"""
            params = []
            if student_id:
                sql += " AND cr.student_id = ?"
                params.append(student_id)
            if consent_type:
                sql += " AND cr.consent_type = ?"
                params.append(consent_type)
            if granted_only:
                sql += " AND cr.granted = 1"
            sql += " ORDER BY s.last_name, cr.consent_type"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def toggle_granted(self, record_id, granted):
        conn = self._conn()
        try:
            conn.execute("UPDATE consent_records SET granted = ?, updated_at = datetime('now') WHERE id = ?",
                         (int(granted), record_id))
            conn.commit()
        finally:
            conn.close()

    def delete_record(self, record_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM consent_records WHERE id = ?", (record_id,))
            conn.commit()
        finally:
            conn.close()

    def summary_by_type(self):
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT consent_type, COUNT(*) as total,
                          SUM(granted) as granted_count
                   FROM consent_records WHERE status = 'active'
                   GROUP BY consent_type ORDER BY consent_type"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
