"""StudentWellbeingService service for the Secondary School."""

import logging

from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


#: Columns accepted by create/update. Keeping this list aligned with
#: ``wellbeing_referrals`` in ``schema.py`` makes every SQL statement in this
#: module fully static — user-controlled keys are never concatenated into SQL.
_WRITE_COLUMNS: tuple[str, ...] = (
    "student_id",
    "referred_by",
    "concern_type",
    "description",
    "risk_level",
    "status",
)

#: Columns on which filtering is allowed by ``list_all``.
_FILTER_COLUMNS: frozenset[str] = frozenset(_WRITE_COLUMNS)


class StudentWellbeingService:
    """CRUD operations for wellbeing referral."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create(self, **kwargs):
        """Create a new wellbeing referral record.

        Only columns in :data:`_WRITE_COLUMNS` are accepted; missing fields
        default to SQL ``NULL`` (or the schema default) and any unknown key is
        rejected before SQL is built.
        """
        unknown = set(kwargs) - set(_WRITE_COLUMNS)
        if unknown:
            raise ValueError(f"Unknown column(s): {sorted(unknown)}")
        conn = self._conn()
        try:
            cursor = conn.cursor()
            # Columns with schema defaults are wrapped in COALESCE so an
            # omitted value resolves to the default rather than to NULL.
            cursor.execute(
                """INSERT INTO wellbeing_referrals (
                    student_id, referred_by, concern_type, description,
                    risk_level, status
                ) VALUES (?, ?, ?, ?, COALESCE(?, 'Low'), COALESCE(?, 'Open'))""",
                (
                    kwargs.get("student_id"),
                    kwargs.get("referred_by"),
                    kwargs.get("concern_type"),
                    kwargs.get("description"),
                    kwargs.get("risk_level"),
                    kwargs.get("status"),
                ),
            )
            conn.commit()
            return cursor.lastrowid
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_all(self, limit=100, offset=0, **filters):
        """List wellbeing referral records with optional filters.

        Only keys listed in :data:`_FILTER_COLUMNS` are honoured; anything else
        raises ``ValueError`` before any SQL is built. The column names in the
        built SQL therefore always come from the in-module whitelist, never
        from the caller's strings.
        """
        unknown = set(filters) - _FILTER_COLUMNS
        if unknown:
            raise ValueError(f"Unknown filter column(s): {sorted(unknown)}")

        # Column-name → literal-SQL-fragment map. Every fragment is a constant
        # string so CodeQL sees no taint flow into the query text.
        _FILTER_SQL: dict[str, str] = {
            "student_id": " AND student_id = ?",
            "referred_by": " AND referred_by = ?",
            "concern_type": " AND concern_type = ?",
            "description": " AND description = ?",
            "risk_level": " AND risk_level = ?",
            "status": " AND status = ?",
        }

        conn = self._conn()
        try:
            sql = "SELECT * FROM wellbeing_referrals WHERE 1=1"
            params: list = []
            for key in _WRITE_COLUMNS:  # iterate allowlist, not user keys
                val = filters.get(key)
                if val is not None:
                    sql += _FILTER_SQL[key]
                    params.append(val)
            sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get(self, record_id):
        """Get a single wellbeing referral by ID."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM wellbeing_referrals WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update(self, record_id, **kwargs):
        """Update a wellbeing referral record.

        Uses a fully-static ``UPDATE`` statement; each updatable column is
        wrapped in ``COALESCE(?, col)`` so missing fields leave the existing
        value untouched. No user-controlled identifier is interpolated.
        """
        unknown = set(kwargs) - set(_WRITE_COLUMNS)
        if unknown:
            raise ValueError(f"Unknown column(s): {sorted(unknown)}")
        if not any(kwargs.get(col) is not None for col in _WRITE_COLUMNS):
            return False
        conn = self._conn()
        try:
            conn.execute(
                """UPDATE wellbeing_referrals
                   SET student_id   = COALESCE(?, student_id),
                       referred_by  = COALESCE(?, referred_by),
                       concern_type = COALESCE(?, concern_type),
                       description  = COALESCE(?, description),
                       risk_level   = COALESCE(?, risk_level),
                       status       = COALESCE(?, status),
                       updated_at   = datetime('now')
                   WHERE id = ?""",
                (
                    kwargs.get("student_id"),
                    kwargs.get("referred_by"),
                    kwargs.get("concern_type"),
                    kwargs.get("description"),
                    kwargs.get("risk_level"),
                    kwargs.get("status"),
                    record_id,
                ),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete(self, record_id):
        """Delete a wellbeing referral record."""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM wellbeing_referrals WHERE id = ?", (record_id,))
            conn.commit()
            return True
        finally:
            conn.close()

