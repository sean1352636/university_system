"""Quality assurance management service."""

import logging
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class QualityAssuranceService:
    """Quality assurance management."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create(self, **kwargs):
        # Iterate over a literal allowed-column tuple so user-supplied keys
        # never flow into the SQL identifier positions (py/sql-injection).
        col_names: list[str] = []
        placeholders: list[str] = []
        values: list = []
        for col in ('review_type', 'department', 'reviewer', 'review_date', 'rating', 'strengths', 'areas_for_improvement', 'action_plan', 'follow_up_date', 'status'):
            if col in kwargs and kwargs[col] is not None:
                col_names.append(col)
                placeholders.append("?")
                values.append(kwargs[col])
        if not col_names:
            raise ValueError("No valid fields to insert.")
        cols_sql = ", ".join(col_names)
        ph_sql = ", ".join(placeholders)
        conn = self._conn()
        try:
            cursor = conn.execute(
                f"INSERT INTO qa_reviews ({cols_sql}) VALUES ({ph_sql})",  # noqa: S608
                values,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM qa_reviews WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row) if row else {"id": cursor.lastrowid}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_all(self, limit=100, offset=0, **filters):
        # Iterate over a literal column tuple so filter keys are constrained
        # to known columns; user-supplied filter names cannot reach the SQL.
        where_parts: list[str] = ["1=1"]
        params: list = []
        for col in ('id', 'review_type', 'department', 'reviewer', 'review_date', 'rating', 'strengths', 'areas_for_improvement', 'action_plan', 'follow_up_date', 'status'):
            val = filters.get(col)
            if val is not None:
                where_parts.append(f"{col} = ?")
                params.append(val)
        where_clause = " AND ".join(where_parts)
        params.extend([limit, offset])
        conn = self._conn()
        try:
            sql = (
                f"SELECT * FROM qa_reviews WHERE {where_clause} "  # noqa: S608
                "ORDER BY id DESC LIMIT ? OFFSET ?"
            )
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get(self, record_id):
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM qa_reviews WHERE id = ?", (record_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update(self, record_id, **kwargs):
        if not kwargs:
            return None
        set_parts: list[str] = []
        values: list = []
        for col in ('review_type', 'department', 'reviewer', 'review_date', 'rating', 'strengths', 'areas_for_improvement', 'action_plan', 'follow_up_date', 'status'):
            if col in kwargs:
                set_parts.append(f"{col} = ?")
                values.append(kwargs[col])
        if not set_parts:
            return None
        set_clause = ", ".join(set_parts)
        values.append(record_id)
        conn = self._conn()
        try:
            conn.execute(
                f"UPDATE qa_reviews SET {set_clause} WHERE id = ?",  # noqa: S608
                values,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM qa_reviews WHERE id = ?", (record_id,)
            ).fetchone()
            return dict(row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete(self, record_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM qa_reviews WHERE id = ?", (record_id,))
            conn.commit()
            return True
        finally:
            conn.close()

