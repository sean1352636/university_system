"""SQLite implementation kept outside university domain packages."""

from __future__ import annotations

from typing import Any

from education_system.systems.university.infrastructure.database.db import get_connection


class SQLiteUnitOfWork:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path
        self.connection: Any = None
        self._committed = False

    def __enter__(self) -> "SQLiteUnitOfWork":
        self.connection = get_connection(self.db_path)
        self.connection.execute("BEGIN IMMEDIATE")
        return self

    def commit(self) -> None:
        self.connection.commit()
        self._committed = True

    def rollback(self) -> None:
        self.connection.rollback()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        try:
            if exc_type is not None or not self._committed:
                self.rollback()
        finally:
            self.connection.close()
        return False


__all__ = ["SQLiteUnitOfWork"]
