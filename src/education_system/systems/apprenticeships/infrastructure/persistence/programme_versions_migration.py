"""Rebuild ``programmes`` so versions of one standard can share a reference.

The table was created with ``reference TEXT NOT NULL UNIQUE``. Programme
versioning keeps every version of a standard as its own row — so the
apprentices on version 1.0 keep it while new starts go onto 1.1 — and
both rows carry the same IfATE reference. The uniqueness therefore has
to move to ``(reference, version)``.

SQLite cannot drop a column constraint in place, so this follows its
documented rebuild procedure: foreign keys off, copy into a new table,
drop the old one, rename the new one into place, check nothing now
dangles, foreign keys back on. Foreign keys MUST be off for the drop —
with them on, dropping ``programmes`` would cascade-delete every KSB,
duty, degree link and curriculum module that points at it.

Idempotent: it checks for the old constraint first and does nothing once
the table has been rebuilt, so it is safe to run on every start.
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

_TEMP_TABLE = "programmes__versioned"

# Keep in step with the programmes definition in schema.SCHEMA. The column
# list is compared in tests, so drift fails loudly rather than silently.
_PROGRAMMES_DDL = f"""
CREATE TABLE {_TEMP_TABLE} (
    programme_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    reference         TEXT    NOT NULL,
    title             TEXT    NOT NULL,
    level             INTEGER NOT NULL,
    funding_band      INTEGER NOT NULL,
    duration_months   INTEGER NOT NULL,
    epa_methods       TEXT,
    sector            TEXT,
    description       TEXT,
    status            TEXT    NOT NULL DEFAULT 'Draft',
    version           TEXT    NOT NULL DEFAULT '1.0',
    supersedes_programme_id INTEGER,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (supersedes_programme_id)
        REFERENCES programmes(programme_id) ON DELETE SET NULL,
    UNIQUE (reference, version)
)
"""


def reference_is_unique_alone(conn: sqlite3.Connection) -> bool:
    """Does ``programmes`` still carry a UNIQUE index on reference by itself?"""
    for index in conn.execute("PRAGMA index_list(programmes)").fetchall():
        name, unique = index[1], index[2]
        if not unique:
            continue
        columns = [
            r[0] for r in conn.execute(
                "SELECT name FROM pragma_index_info(?) ORDER BY seqno", (name,)
            ).fetchall()
        ]
        if columns == ["reference"]:
            return True
    return False


def allow_versions_to_share_a_reference(conn: sqlite3.Connection) -> None:
    """Rebuild ``programmes`` with ``UNIQUE (reference, version)``, once."""
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'programmes'"
    ).fetchone():
        return
    if not reference_is_unique_alone(conn):
        return

    # PRAGMA foreign_keys is a no-op inside a transaction, so settle any
    # open one first, then prove it really is off before dropping anything.
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    if conn.execute("PRAGMA foreign_keys").fetchone()[0]:
        conn.execute("PRAGMA foreign_keys = ON")
        raise RuntimeError(
            "Could not switch foreign keys off to rebuild the programmes table; "
            "refusing to drop it, as that would cascade-delete its KSBs and duties."
        )
    try:
        conn.execute("BEGIN IMMEDIATE")
        # Another process may have rebuilt it while this one waited.
        if not reference_is_unique_alone(conn):
            conn.execute("ROLLBACK")
            return
        _rebuild(conn)
        conn.execute("COMMIT")
        logger.info("Rebuilt programmes: reference is now unique per version")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        logger.exception("Rebuilding the programmes table failed; left unchanged")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _rebuild(conn: sqlite3.Connection) -> None:
    violations_before = set(_violations(conn))

    # Indexes and triggers go with the dropped table; keep their SQL so
    # they can be put back on the new one. The autoindex behind the old
    # UNIQUE has no SQL and is deliberately not carried over.
    extras = [
        r[0] for r in conn.execute(
            "SELECT sql FROM sqlite_master WHERE tbl_name = 'programmes' "
            "AND type IN ('index', 'trigger') AND sql IS NOT NULL"
        ).fetchall()
    ]

    old_columns = [r[1] for r in conn.execute("PRAGMA table_info(programmes)").fetchall()]
    conn.execute(f"DROP TABLE IF EXISTS {_TEMP_TABLE}")
    conn.execute(_PROGRAMMES_DDL)
    new_columns = [r[1] for r in conn.execute(f"PRAGMA table_info({_TEMP_TABLE})").fetchall()]
    # Column names come from PRAGMA on this codebase's own tables, never
    # from user input.
    shared = ", ".join(c for c in new_columns if c in old_columns)
    conn.execute(
        f"INSERT INTO {_TEMP_TABLE} ({shared}) SELECT {shared} FROM programmes"  # noqa: S608
    )
    before = conn.execute("SELECT COUNT(*) FROM programmes").fetchone()[0]
    after = conn.execute(f"SELECT COUNT(*) FROM {_TEMP_TABLE}").fetchone()[0]  # noqa: S608
    if before != after:
        raise RuntimeError(f"Copied {after} of {before} programmes; aborting the rebuild")

    conn.execute("DROP TABLE programmes")
    # Legacy rename: do not re-parse views and triggers elsewhere, which
    # would trip over the moment ``programmes`` does not exist.
    conn.execute("PRAGMA legacy_alter_table = ON")
    try:
        conn.execute(f"ALTER TABLE {_TEMP_TABLE} RENAME TO programmes")
    finally:
        conn.execute("PRAGMA legacy_alter_table = OFF")
    for statement in extras:
        conn.execute(statement)

    introduced = set(_violations(conn)) - violations_before
    if introduced:
        raise RuntimeError(
            f"Rebuilding programmes would leave {len(introduced)} dangling reference(s)"
        )


def _violations(conn: sqlite3.Connection) -> list[tuple]:
    return [tuple(r) for r in conn.execute("PRAGMA foreign_key_check").fetchall()]
