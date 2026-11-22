"""primary: point parents' evening and trip bookings at the pupils table

``parents_evening_bookings`` and ``trip_bookings`` in primary.db were ported from
the sixth form with ``FOREIGN KEY (student_id) REFERENCES students(student_id)``.
Primary has no ``students`` table and foreign keys are on, so every insert or
update on either table failed with "no such table: main.students", and the
booking and consent screens could not save anything.

SQLite cannot alter a foreign key, so each table is rebuilt with the same columns
and rows, pointing at ``pupils(pupil_id)``. This is the one step here that is not
purely additive; nothing is dropped except the broken constraint.

primary.db is not this Alembic chain's own database. It is opened directly, only
when this upgrade is running against the real student_records.db, so a test that
upgrades a temporary database cannot reach the live file. Idempotent: a table whose
foreign key is already right, or a database or table that does not exist, is
skipped.

Revision ID: f6a8c0e2b4d6
Revises: e5b7d9f1a3c5
Create Date: 2026-11-01 10:00:00.000000
"""
import logging
import os
import sqlite3
from typing import Sequence, Union

from alembic import op

from education_system import paths


revision: str = 'f6a8c0e2b4d6'
down_revision: Union[str, Sequence[str], None] = 'e5b7d9f1a3c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)

TABLES = ("parents_evening_bookings", "trip_bookings")


def _rebuild(conn: sqlite3.Connection, table: str) -> bool:
    """Rebuild *table* if its foreign key names ``students``. True if it did."""
    fks = conn.execute(f'PRAGMA foreign_key_list("{table}")').fetchall()  # nosec B608
    if not any(fk[2] == "students" for fk in fks):
        return False
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                       (table,)).fetchone()
    new_table = f"{table}__rebuild"
    create = row[0].replace(f"CREATE TABLE {table}", f"CREATE TABLE {new_table}", 1)
    create = create.replace("REFERENCES students(student_id)", "REFERENCES pupils(pupil_id)")
    indexes = [r[0] for r in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND tbl_name = ? "
        "AND sql IS NOT NULL", (table,)).fetchall()]
    conn.execute(f'DROP TABLE IF EXISTS "{new_table}"')  # nosec B608
    conn.execute(create)
    conn.execute(f'INSERT INTO "{new_table}" SELECT * FROM "{table}"')  # nosec B608
    conn.execute(f'DROP TABLE "{table}"')  # nosec B608
    conn.execute(f'ALTER TABLE "{new_table}" RENAME TO "{table}"')  # nosec B608
    for sql in indexes:
        conn.execute(sql)
    return True


def repair(db_path: str) -> list[str]:
    """Repair the foreign keys in the database at *db_path*; the tables rebuilt."""
    if not os.path.exists(db_path):
        return []
    # isolation_level=None: PRAGMA foreign_keys is ignored inside a transaction.
    conn = sqlite3.connect(db_path, isolation_level=None, timeout=30)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")}
            done = [t for t in TABLES if t in existing and "pupils" in existing
                    and _rebuild(conn, t)]
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return done
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.close()


def _upgrading_the_real_database() -> bool:
    database = op.get_bind().engine.url.database
    if not database:
        return False
    return (os.path.realpath(database)
            == os.path.realpath(str(paths.SYSTEM_DB_PATHS.get("university", ""))))


def upgrade() -> None:
    if not _upgrading_the_real_database():
        return
    try:
        done = repair(str(paths.PRIMARY_PUPILS_DB))
    except sqlite3.Error:
        # A bad primary.db must not stop the other six systems from starting.
        logger.exception("Could not repair primary booking foreign keys")
        return
    if done:
        logger.info("Repaired primary booking foreign keys: %s", done)


def downgrade() -> None:
    """Nothing to undo: the old foreign key could not work."""
