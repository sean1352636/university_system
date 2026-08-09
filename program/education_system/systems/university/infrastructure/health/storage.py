"""Health repository connection adapter.

All health callers import this module instead of the general student database.
Only the opaque student identifier is shared across the storage boundary.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from education_system.systems.university.infrastructure.database import db as _db
from education_system.paths import UNIVERSITY_HEALTH_DB_PATH

DEFAULT_DB_PATH = UNIVERSITY_HEALTH_DB_PATH
DatabaseManager = _db.DatabaseManager
sqlite3 = _db.sqlite3


def get_connection(db_path: Any = None, *args: Any, **kwargs: Any):
    target = db_path or UNIVERSITY_HEALTH_DB_PATH
    # Health storage is intentionally isolated from the general student DB;
    # ensure its runtime directory exists even when this subsystem is invoked
    # directly rather than through the main bootstrap sequence.
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except AttributeError:
        pass
    return _db.get_connection(target, *args, **kwargs)


@contextmanager
def transaction(db_path: Any = None, row_factory: bool = True) -> Iterator[Any]:
    with _db.transaction(db_path or UNIVERSITY_HEALTH_DB_PATH, row_factory=row_factory) as connection:
        yield connection


__all__ = ["DEFAULT_DB_PATH", "DatabaseManager", "get_connection", "sqlite3", "transaction"]
