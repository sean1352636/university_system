"""Retention helpers for safeguarding and SCR tables.

KCSIE expects a child's safeguarding file to outlive their enrolment
(it moves with them, and is kept until they are 25 by default). The
first schemas here used ``ON DELETE CASCADE`` to ``students`` /
``staff``, so deleting a student silently wiped their concerns.

SQLite cannot drop a foreign-key clause in place, so
:func:`rebuild_table` performs the documented rebuild once, lazily, the
first time a module's ``init_db`` sees a cascade in the live schema:

1. back up the whole database file to
   ``paths.system_backup_dir("sixth_form", <label>)``;
2. ``PRAGMA foreign_keys=OFF`` then one transaction;
3. create ``<table>__rebuild`` from the new DDL, copy every row
   (shared columns only), drop the old table, rename the new one;
4. recreate the table's indexes;
5. ``PRAGMA foreign_key_check`` — any violation rolls the whole thing
   back;
6. ``PRAGMA foreign_keys=ON``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from pathlib import Path

from education_system import paths

logger = logging.getLogger(__name__)

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _ident(name: str) -> str:
    if not _IDENT_RE.match(name or ""):
        raise ValueError(f"Bad identifier: {name!r}")
    return name


def table_sql(conn: _sql.Connection, table: str) -> str | None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table,)).fetchone()
    return row[0] if row else None


def has_cascade(conn: _sql.Connection, table: str) -> bool:
    sql = table_sql(conn, table) or ""
    return "ON DELETE CASCADE" in re.sub(r"\s+", " ", sql.upper())


def columns(conn: _sql.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(
        f"PRAGMA table_info({_ident(table)})")]  # DBW001: validated identifier


def add_missing_columns(conn: _sql.Connection, table: str,
                        wanted: dict[str, str]) -> None:
    """``ALTER TABLE ADD COLUMN`` for each *wanted* name not yet present."""
    have = set(columns(conn, table))
    for name, decl in wanted.items():
        if name not in have:
            conn.execute(
                f"ALTER TABLE {_ident(table)} ADD COLUMN "  # DBW001: validated identifiers, literal decl
                f"{_ident(name)} {decl}")


def backup_database(db_path: Path | str, label: str,
                    table: str = "") -> Path:
    """Copy the whole SQLite file with the online backup API."""
    dest_dir = paths.system_backup_dir("sixth_form", label)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    suffix = f"_before_{table}" if table else ""
    dest = dest_dir / f"{Path(db_path).stem}_{stamp}{suffix}.db"
    src = _sql.connect(str(db_path))
    try:
        dst = _sql.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    logger.warning("Backed up %s to %s before a retention rebuild",
                   db_path, dest)
    return dest


def rebuild_table(db_path: Path | str, table: str, create_sql: str, *,
                  label: str, extra_copy: dict[str, str] | None = None
                  ) -> bool:
    """Safe wrapper: a failed rebuild is logged, never blocks the caller.

    A DSL mid-incident must still be able to open the record; the
    rebuild is retried on the next launch.
    """
    try:
        return _rebuild_table(db_path, table, create_sql, label=label,
                              extra_copy=extra_copy)
    except (_sql.Error, OSError):
        logger.exception("Retention rebuild of %s failed; will retry on "
                         "next start", table)
        return False


def _rebuild_table(db_path: Path | str, table: str, create_sql: str, *,
                   label: str, extra_copy: dict[str, str] | None = None
                   ) -> bool:
    """Rebuild *table* from *create_sql* if its live DDL has a cascade.

    *create_sql* must be a ``CREATE TABLE {name} (...)`` template; the
    ``{name}`` placeholder is filled with the temporary table name.
    *extra_copy* maps new-column -> SQL expression over the old table
    (e.g. a name snapshot pulled from ``students``) for columns that the
    old table did not have.

    Returns True when a rebuild happened. Never runs twice: once the
    cascade is gone :func:`has_cascade` is False.
    """
    table = _ident(table)
    conn = _sql.connect(str(db_path), isolation_level=None)
    try:
        if not has_cascade(conn, table):
            return False
        index_sql = [r[0] for r in conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' "
            "AND tbl_name=? AND sql IS NOT NULL", (table,))]
        old_cols = columns(conn, table)
    finally:
        conn.close()

    backup_database(db_path, label, table)

    tmp = f"{table}__rebuild"
    conn = _sql.connect(str(db_path), isolation_level=None)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("PRAGMA legacy_alter_table=ON")
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(f"DROP TABLE IF EXISTS {tmp}")  # DBW001: validated identifier
            conn.execute(create_sql.format(name=tmp))
            new_cols = columns(conn, tmp)
            shared = [c for c in old_cols if c in new_cols]
            dest_cols = list(shared)
            src_exprs = [f'"{c}"' for c in shared]
            for col, expr in (extra_copy or {}).items():
                if col in new_cols and col not in shared:
                    dest_cols.append(col)
                    src_exprs.append(expr)
            conn.execute(
                f"INSERT INTO {tmp} ({', '.join(_ident(c) for c in dest_cols)}) "  # DBW001: validated identifiers
                f"SELECT {', '.join(src_exprs)} FROM {table} AS old")
            n_old = conn.execute(
                f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # DBW001: validated identifier
            n_new = conn.execute(
                f"SELECT COUNT(*) FROM {tmp}").fetchone()[0]  # DBW001: validated identifier
            if n_old != n_new:
                raise _sql.DatabaseError(
                    f"Row count mismatch rebuilding {table}: "
                    f"{n_old} -> {n_new}")
            conn.execute(f"DROP TABLE {table}")  # DBW001: validated identifier
            conn.execute(f"ALTER TABLE {tmp} RENAME TO {table}")  # DBW001: validated identifiers
            for sql in index_sql:
                conn.execute(sql)
            bad = conn.execute("PRAGMA foreign_key_check").fetchall()
            bad = [b for b in bad if b[0] == table]
            if bad:
                raise _sql.IntegrityError(
                    f"foreign_key_check failed after rebuilding {table}: "
                    f"{bad[:5]}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            logger.exception("Retention rebuild of %s rolled back", table)
            raise
        finally:
            conn.execute("PRAGMA legacy_alter_table=OFF")
            conn.execute("PRAGMA foreign_keys=ON")
    finally:
        conn.close()
    logger.warning("Rebuilt %s without ON DELETE CASCADE (%d rows kept)",
                   table, n_new)
    return True
