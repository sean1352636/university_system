"""Prevent duty management service."""

import logging
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class PreventDutyService:
    """Prevent duty management."""

    ALLOWED_COLUMNS = {
        "student_id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "referral_reason",
        "risk_level",
        "notes",
        "status",
        "referred_at",
        "updated_at",
    }

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def _sanitize_fields(self, fields: dict, allow_empty: bool = False, drop_none: bool = False) -> dict:
        sanitized = {}
        for key, value in fields.items():
            if key not in self.ALLOWED_COLUMNS:
                raise ValueError(f"Invalid field: {key}")
            if drop_none and value is None:
                continue
            sanitized[key] = value

        if not allow_empty and not sanitized:
            raise ValueError("No valid fields provided.")
        return sanitized

    def create(self, **kwargs):
        conn = self._conn()
        try:
            safe_kwargs = self._sanitize_fields(kwargs)
            cols = ", ".join(safe_kwargs.keys())
            placeholders = ", ".join("?" for _ in safe_kwargs)
            cursor = conn.execute(
                f"INSERT INTO prevent_referrals ({cols}) VALUES ({placeholders})",
                list(safe_kwargs.values()))
            conn.commit()
            row = conn.execute("SELECT * FROM prevent_referrals WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row) if row else {"id": cursor.lastrowid}
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_all(self, limit=100, offset=0, **filters):
        conn = self._conn()
        try:
            safe_filters = self._sanitize_fields(filters, allow_empty=True, drop_none=True)
            sql = "SELECT * FROM prevent_referrals WHERE 1=1"
            params = []
            for key, val in safe_filters.items():
                sql += f" AND {key} = ?"
                params.append(val)
            sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get(self, record_id):
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM prevent_referrals WHERE id = ?", (record_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update(self, record_id, **kwargs):
        if not kwargs:
            return None
        conn = self._conn()
        try:
            safe_kwargs = self._sanitize_fields(kwargs)
            set_clause = ", ".join(f"{k} = ?" for k in safe_kwargs)
            values = list(safe_kwargs.values()) + [record_id]
            conn.execute(f"UPDATE prevent_referrals SET {set_clause} WHERE id = ?", values)
            conn.commit()
            row = conn.execute("SELECT * FROM prevent_referrals WHERE id = ?", (record_id,)).fetchone()
            return dict(row) if row else None
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete(self, record_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM prevent_referrals WHERE id = ?", (record_id,))
            conn.commit()
            return True
        finally:
            conn.close()

