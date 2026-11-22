"""What would a DELETE destroy? Count the rows that reference a record.

Every Sixth Form table lives in one database with foreign keys ON, and
many references are ``ON DELETE CASCADE``: deleting a course silently
takes its class groups, their timetable slots and every attendance mark
recorded against them. Delete functions use this module to look before
they leap and refuse (offering archive instead) when history would go.

The walk reads the schema (``pragma_foreign_key_list``), so a table
added later is covered without being listed anywhere:

* :func:`cascade_counts` — rows a delete would remove through
  ``CASCADE`` (followed transitively) or that would make SQLite refuse
  it (``RESTRICT`` / ``NO ACTION``). ``SET NULL`` / ``SET DEFAULT``
  references survive the delete, so they are not counted.
* :func:`soft_counts` — rows in tables that hold the id *without* a
  foreign key (logs, cover requests, lesson plans …) and would be left
  pointing at nothing.
* :func:`describe` — "12 attendance records, 3 register sessions" for
  a refusal message.

Generalises ``students.linked_record_counts`` (the Student Directory's
guard) so other delete paths can share it.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any, Iterable

logger = logging.getLogger(__name__)

_CHUNK = 500
_DEFAULT_DEPTH = 8


def _q(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,)).fetchone() is not None


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(
        "SELECT * FROM pragma_table_info(?)", (table,))}


def _pk_column(conn: sqlite3.Connection, table: str) -> str:
    pks = [r[1] for r in conn.execute(
        "SELECT * FROM pragma_table_info(?)", (table,)) if r[5]]
    return pks[0] if len(pks) == 1 else "rowid"


def _references_to(conn: sqlite3.Connection,
                   table: str) -> list[tuple[str, str, str, str]]:
    """``(child, child_col, parent_col, on_delete)`` for every single-column
    foreign key that points at *table*."""
    groups: dict[tuple[str, int], list[Any]] = {}
    for child, fk_id, frm, to, on_delete in conn.execute(
            "SELECT m.name, f.id, f.\"from\", f.\"to\", f.on_delete "
            "FROM sqlite_master m JOIN pragma_foreign_key_list(m.name) f "
            "WHERE m.type = 'table' AND f.\"table\" = ? COLLATE NOCASE",
            (table,)):
        groups.setdefault((child, fk_id), []).append((frm, to, on_delete))
    out: list[tuple[str, str, str, str]] = []
    for (child, _fk), cols in groups.items():
        if len(cols) != 1:          # composite keys: not used here
            continue
        frm, to, on_delete = cols[0]
        out.append((child, frm, to or _pk_column(conn, table),
                    str(on_delete or "NO ACTION").upper()))
    return out


def _chunks(values: list[Any]) -> Iterable[list[Any]]:
    for i in range(0, len(values), _CHUNK):
        yield values[i:i + _CHUNK]


def _walk(conn: sqlite3.Connection, table: str, rowids: list[int],
          out: dict[str, int], seen: set[tuple[str, int]], depth: int) -> None:
    if not rowids or depth <= 0:
        return
    for child, frm, to, action in _references_to(conn, table):
        if action in ("SET NULL", "SET DEFAULT"):
            continue
        vals: set[Any] = set()
        for part in _chunks(rowids):
            ph = ",".join("?" * len(part))
            # db-audit: ignore[DBW001] - identifiers come from sqlite_master/pragma and are quoted
            vals.update(r[0] for r in conn.execute(
                f"SELECT {_q(to)} FROM {_q(table)} WHERE rowid IN ({ph})",
                part) if r[0] is not None)
        if not vals:
            continue
        found: list[int] = []
        try:
            for part in _chunks(sorted(vals, key=str)):
                ph = ",".join("?" * len(part))
                # db-audit: ignore[DBW001] - identifiers come from sqlite_master/pragma and are quoted
                found.extend(r[0] for r in conn.execute(
                    f"SELECT rowid FROM {_q(child)} WHERE {_q(frm)} IN ({ph})",
                    part))
        except sqlite3.OperationalError:
            # WITHOUT ROWID table: count it, but it cannot be walked further.
            n = 0
            for part in _chunks(sorted(vals, key=str)):
                ph = ",".join("?" * len(part))
                # db-audit: ignore[DBW001] - identifiers come from sqlite_master/pragma and are quoted
                n += conn.execute(
                    f"SELECT COUNT(*) FROM {_q(child)} WHERE {_q(frm)} IN ({ph})",
                    part).fetchone()[0]
            if n:
                out[child] = out.get(child, 0) + n
            continue
        new = [r for r in found if (child, r) not in seen]
        seen.update((child, r) for r in new)
        if not new:
            continue
        out[child] = out.get(child, 0) + len(new)
        if action == "CASCADE":
            _walk(conn, child, new, out, seen, depth - 1)


def cascade_counts(conn: sqlite3.Connection, table: str, column: str,
                   value: Any, *, max_depth: int = _DEFAULT_DEPTH
                   ) -> dict[str, int]:
    """``{table: rows}`` that ``DELETE FROM table WHERE column = value``
    would remove (cascades, followed transitively) or be refused by."""
    if not has_table(conn, table):
        return {}
    # db-audit: ignore[DBW001] - table/column are caller constants, quoted
    rowids = [r[0] for r in conn.execute(
        f"SELECT rowid FROM {_q(table)} WHERE {_q(column)} = ?", (value,))]
    out: dict[str, int] = {}
    seen = {(table, r) for r in rowids}
    _walk(conn, table, rowids, out, seen, max_depth)
    return out


def soft_counts(conn: sqlite3.Connection,
                refs: Iterable[tuple[str, str]], value: Any) -> dict[str, int]:
    """``{table: rows}`` for ``(table, column)`` references that have no
    foreign key — a delete leaves these rows pointing at nothing. Tables
    or columns that do not exist yet are skipped."""
    out: dict[str, int] = {}
    for table, col in refs:
        if not has_table(conn, table) or col not in columns(conn, table):
            continue
        try:
            # db-audit: ignore[DBW001] - identifiers are caller constants, quoted
            n = conn.execute(
                f"SELECT COUNT(*) FROM {_q(table)} WHERE {_q(col)} = ?",
                (value,)).fetchone()[0]
        except sqlite3.Error:
            logger.exception("Could not count %s.%s", table, col)
            continue
        if n:
            out[table] = out.get(table, 0) + int(n)
    return out


def tables_with_column(conn: sqlite3.Connection, column: str, *,
                       exclude: Iterable[str] = ()) -> list[tuple[str, str]]:
    """``(table, column)`` for every table holding *column* without a
    foreign key on it (the FK ones are covered by :func:`cascade_counts`)."""
    skip = set(exclude)
    out: list[tuple[str, str]] = []
    for (t,) in conn.execute(
            "SELECT m.name FROM sqlite_master m JOIN pragma_table_info(m.name) c "
            "WHERE m.type = 'table' AND c.name = ?", (column,)):
        if t in skip or t.startswith("sqlite_"):
            continue
        fk_cols = {r[3] for r in conn.execute(
            "SELECT * FROM pragma_foreign_key_list(?)", (t,))}
        if column not in fk_cols:
            out.append((t, column))
    return out


def merge(*parts: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for p in parts:
        for k, v in p.items():
            if v:
                out[k] = out.get(k, 0) + v
    return out


def describe(counts: dict[str, int], *, limit: int = 8) -> str:
    """``"12 attendance records, 3 register sessions"`` (largest first)."""
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    words = [f"{n} {t.replace('_', ' ')}" for t, n in items[:limit]]
    if len(items) > limit:
        words.append(f"{len(items) - limit} more area(s)")
    return ", ".join(words)
