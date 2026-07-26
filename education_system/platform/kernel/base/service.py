"""Base service class with common CRUD patterns and connection management.

Improvement #2: Deduplicate Service Patterns
"""

import logging
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class BaseService:
    """Base class for all service layers across education systems.

    Provides connection management, generic CRUD operations,
    pagination, and search.

    Usage:
        class StudentService(BaseService):
            TABLE = "students"
            ID_COLUMN = "student_id"
            SEARCHABLE_COLUMNS = ["first_name", "last_name", "email"]
    """

    TABLE: str = ""
    ID_COLUMN: str = "id"
    SEARCHABLE_COLUMNS: list[str] = []

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        from education_system.platform.identity.auth.db import connect
        return connect(self._db_path)

    @contextmanager
    def _conn(self, *, commit: bool = False):
        """Context manager for database connections.

        with self._conn() as conn:           # read-only, auto-closes
        with self._conn(commit=True) as conn: # auto-commits or rolls back
        """
        conn = self._connect()
        try:
            yield conn
            if commit:
                conn.commit()
        except Exception:
            if commit:
                conn.rollback()
            raise
        finally:
            conn.close()

    def get_by_id(self, record_id) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.TABLE} WHERE {self.ID_COLUMN} = ?", (record_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_all(self, *, limit: int = 100, offset: int = 0,
                 order_by: str | None = None, filters: dict | None = None) -> list[dict]:
        conditions, params = [], []
        if filters:
            for col, val in filters.items():
                if val is not None:
                    if not col.replace("_", "").isalnum():
                        raise ValueError(f"Invalid column name: {col}")
                    conditions.append(f"{col} = ?")
                    params.append(val)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        order = ""
        if order_by and order_by.replace("_", "").replace(" ", "").replace(",", "").isalnum():
            order = f"ORDER BY {order_by}"
        params.extend([limit, offset])

        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM {self.TABLE} {where} {order} LIMIT ? OFFSET ?", params
            ).fetchall()
            return [dict(r) for r in rows]

    def count(self, *, filters: dict | None = None) -> int:
        conditions, params = [], []
        if filters:
            for col, val in filters.items():
                if val is not None:
                    if not col.replace("_", "").isalnum():
                        raise ValueError(f"Invalid column name: {col}")
                    conditions.append(f"{col} = ?")
                    params.append(val)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._conn() as conn:
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM {self.TABLE} {where}", params).fetchone()
            return row["cnt"]

    def search(self, query: str, *, limit: int = 50) -> list[dict]:
        if not self.SEARCHABLE_COLUMNS or not query:
            return []
        conditions, params = [], []
        for col in self.SEARCHABLE_COLUMNS:
            if col.replace("_", "").isalnum():
                conditions.append(f"{col} LIKE ?")
                params.append(f"%{query}%")
        if not conditions:
            return []
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM {self.TABLE} WHERE {' OR '.join(conditions)} LIMIT ?", params
            ).fetchall()
            return [dict(r) for r in rows]

    def insert(self, data: dict) -> int:
        columns, values = [], []
        for col, val in data.items():
            if not col.replace("_", "").isalnum():
                raise ValueError(f"Invalid column name: {col}")
            columns.append(col)
            values.append(val)
        placeholders = ", ".join("?" for _ in values)
        with self._conn(commit=True) as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.TABLE} ({', '.join(columns)}) VALUES ({placeholders})", values)
            return cursor.lastrowid

    def update(self, record_id, data: dict) -> bool:
        if not data:
            return False
        set_parts, values = [], []
        for col, val in data.items():
            if not col.replace("_", "").isalnum():
                raise ValueError(f"Invalid column name: {col}")
            set_parts.append(f"{col} = ?")
            values.append(val)
        values.append(record_id)
        with self._conn(commit=True) as conn:
            cursor = conn.execute(
                f"UPDATE {self.TABLE} SET {', '.join(set_parts)} WHERE {self.ID_COLUMN} = ?", values)
            return cursor.rowcount > 0

    def delete(self, record_id) -> bool:
        with self._conn(commit=True) as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.TABLE} WHERE {self.ID_COLUMN} = ?", (record_id,))
            return cursor.rowcount > 0

    def exists(self, record_id) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT 1 FROM {self.TABLE} WHERE {self.ID_COLUMN} = ?", (record_id,)
            ).fetchone()
            return row is not None
