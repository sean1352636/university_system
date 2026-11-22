"""Health repository connection adapter.

Every health caller — CLI and GUI alike — opens its connection here, so
there is one place that decides where health data lives.

That store is the university database. A separate ``health_records.db`` was
started at some point on the principle that only the opaque student
identifier should cross the boundary, but it was never finished: its
``health_records`` table has five of the nine columns the code writes, its
``lab_results`` and ``health_appointments`` disagree with the schema too,
and every health table in it carries ``FOREIGN KEY (student_id) REFERENCES
students`` against a database that has no ``students`` table. SQLite
foreign keys cannot span attached databases, so that last one cannot be
patched around — an INSERT fails with ``no such table: main.students`` no
matter what is attached.

The university database, by contrast, already holds the complete health
schema and the ``students`` table the foreign keys need, and it is where
the only real health rows are. So that is the store, and the separate file
is left untouched rather than half-used.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import logging

from education_system.systems.university.infrastructure.database import db as _db
from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH, UNIVERSITY_HEALTH_DB_PATH

logger = logging.getLogger(__name__)

# Where health data actually lives — see the module docstring. The legacy
# constant is kept so anything importing it still resolves, but nothing opens
# it: health_records.db is retired (its stranded first-aid rows and settings
# were copied into student_records.db by migration 3c5e7a9b1d4f); the file
# is left for the user to delete.
HEALTH_ONLY_DB_PATH = UNIVERSITY_HEALTH_DB_PATH
DEFAULT_DB_PATH = UNIVERSITY_DEFAULT_DB_PATH
DatabaseManager = _db.DatabaseManager
sqlite3 = _db.sqlite3


def get_connection(db_path: Any = None, *args: Any, **kwargs: Any):
    target = db_path or DEFAULT_DB_PATH
    # Make sure the runtime directory exists even when this subsystem is
    # invoked directly rather than through the main bootstrap sequence.
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except AttributeError:
        pass
    return _db.get_connection(target, *args, **kwargs)


@contextmanager
def transaction(db_path: Any = None, row_factory: bool = True) -> Iterator[Any]:
    with _db.transaction(db_path or DEFAULT_DB_PATH, row_factory=row_factory) as connection:
        yield connection


__all__ = ["DEFAULT_DB_PATH", "DatabaseManager", "get_connection", "sqlite3", "transaction"]
