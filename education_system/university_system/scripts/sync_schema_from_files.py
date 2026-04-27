"""Schema-snapshot loader for student_records.db.

Reads every `*.sql` file under `university_system/data/schema/` and
executes it (CREATE TABLE IF NOT EXISTS) against the target DB. Each
file is the canonical definition of one table — adding a new table to
the schema means dropping a new `.sql` file in that directory.

Two public functions:
  * `sync_schema(db_path, dry_run)` — run every CREATE.
  * `verify_schema(db_path)` — compare live DB against the snapshots
    and report missing tables / column drift.

Used by `run.py` at startup; safe to invoke standalone.
"""

from __future__ import annotations

import argparse
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path("/home/seancatchpole989/education_system")
DEFAULT_DB = REPO_ROOT / "university_system/data/db_files/student_records.db"
SCHEMA_DIR = REPO_ROOT / "university_system/data/schema"

log = logging.getLogger(__name__)


@dataclass
class SyncResult:
    created: list[str] = field(default_factory=list)
    already_exists: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class VerifyResult:
    missing_tables: list[str] = field(default_factory=list)
    column_drift: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    extra_tables: list[str] = field(default_factory=list)


def _table_name_from_sql(sql: str) -> str | None:
    m = re.search(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`\[]?([A-Za-z0-9_]+)[\"`\]]?',
        sql,
        re.IGNORECASE,
    )
    return m.group(1) if m else None


def _columns_from_sql(sql: str) -> set[str]:
    """Crude column-name extractor for verify diffs. Strips comments and
    skips top-level constraint clauses."""
    body_match = re.search(r'\((.*)\)\s*;?\s*$', sql, re.DOTALL)
    if not body_match:
        return set()
    body = body_match.group(1)
    # Strip line comments
    body = re.sub(r'--[^\n]*', '', body)
    parts: list[str] = []
    depth = 0
    cur = []
    in_str: str | None = None
    for ch in body:
        if in_str:
            cur.append(ch)
            if ch == in_str:
                in_str = None
            continue
        if ch in ("'", '"', '`'):
            in_str = ch
            cur.append(ch)
        elif ch == '(':
            depth += 1
            cur.append(ch)
        elif ch == ')':
            depth -= 1
            cur.append(ch)
        elif ch == ',' and depth == 0:
            parts.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append(''.join(cur).strip())
    cols: set[str] = set()
    constraint_kw = ('PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK', 'CONSTRAINT', 'INDEX')
    for p in parts:
        if not p:
            continue
        head = re.split(r'[\s(]', p, maxsplit=1)[0].upper().strip('`"[]')
        if head in constraint_kw:
            continue
        ident = re.match(r'[\"`\[]?([A-Za-z_][A-Za-z0-9_]*)[\"`\]]?', p)
        if ident:
            cols.add(ident.group(1).lower())
    return cols


def sync_schema(db_path: Path = DEFAULT_DB, dry_run: bool = False) -> SyncResult:
    result = SyncResult()
    schema_dir = SCHEMA_DIR
    if not schema_dir.exists():
        log.warning("Schema directory not found: %s", schema_dir)
        return result
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        existing = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        for sql_file in sorted(schema_dir.rglob("*.sql")):
            sql = sql_file.read_text()
            table = _table_name_from_sql(sql) or sql_file.stem
            if table in existing:
                result.already_exists.append(table)
                continue
            if dry_run:
                result.created.append(table)
                continue
            try:
                conn.execute(sql)
                conn.commit()
                result.created.append(table)
            except sqlite3.Error as exc:
                result.failed.append((table, f"{type(exc).__name__}: {exc}"))
    finally:
        conn.close()
    return result


def verify_schema(db_path: Path = DEFAULT_DB) -> VerifyResult:
    result = VerifyResult()
    schema_dir = SCHEMA_DIR
    if not schema_dir.exists():
        return result
    snapshot_tables: dict[str, set[str]] = {}
    for sql_file in schema_dir.rglob("*.sql"):
        sql = sql_file.read_text()
        name = _table_name_from_sql(sql)
        if name:
            snapshot_tables[name] = _columns_from_sql(sql)
    conn = sqlite3.connect(str(db_path))
    try:
        live_tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )}
        for table, snap_cols in snapshot_tables.items():
            if table not in live_tables:
                result.missing_tables.append(table)
                continue
            live_cols = {r[1].lower() for r in conn.execute(f'PRAGMA table_info("{table}")')}
            missing = sorted(snap_cols - live_cols)
            extra = sorted(live_cols - snap_cols)
            if missing or extra:
                result.column_drift[table] = {
                    "missing_in_live": missing,
                    "extra_in_live": extra,
                }
        result.extra_tables = sorted(live_tables - set(snapshot_tables))
    finally:
        conn.close()
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = p.add_mutually_exclusive_group()
    sub.add_argument("--sync", action="store_true", help="Apply CREATE TABLE IF NOT EXISTS for every snapshot")
    sub.add_argument("--dry-run", action="store_true")
    sub.add_argument("--verify", action="store_true", help="Diff live DB against snapshots")
    args = p.parse_args()

    if args.verify:
        v = verify_schema(args.db)
        print(f"Missing tables: {len(v.missing_tables)}")
        for t in v.missing_tables:
            print(f"  - {t}")
        print(f"\nColumn drift: {len(v.column_drift)} tables")
        for t, d in v.column_drift.items():
            print(f"  {t}: missing={d['missing_in_live']} extra={d['extra_in_live']}")
        print(f"\nExtra live tables (not in snapshots): {len(v.extra_tables)}")
        return

    r = sync_schema(args.db, dry_run=args.dry_run)
    verb = "would create" if args.dry_run else "created"
    print(f"{verb}: {len(r.created)}")
    print(f"already exists: {len(r.already_exists)}")
    if r.failed:
        print(f"failed: {len(r.failed)}")
        for t, e in r.failed[:20]:
            print(f"  ! {t}: {e}")


if __name__ == "__main__":
    main()
