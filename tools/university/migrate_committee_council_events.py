#!/usr/bin/env python3
"""Fold public_events, sc_events and committee_meetings into ``unified_events``.

Each legacy row becomes a ``unified_events`` row tagged by source:

=====================  =================  ==============================
legacy table           ``source_type``    ``source_event_id``
=====================  =================  ==============================
``public_events``      ``community``      ``public_events:<event_id>``
``sc_events``          ``student_council`` ``sc_events:<id>``
``committee_meetings`` ``committee``      ``committee_meetings:<id>``
=====================  =================  ==============================

``source_event_id`` is namespaced by table because the live database also has
a *non-partial* unique index on ``source_event_id`` alone
(``idx_unified_events_source_id``): a bare ``1`` from two tables would collide.

``committee_agenda_items`` and ``committee_votes`` hold a foreign key to the
meeting. SQLite cannot alter a foreign key, so both are rebuilt pointing at
``unified_events(event_id)`` with ``meeting_id`` remapped. Foreign keys are
enforced everywhere, so the target is the table itself, never a view.

The legacy tables are dropped: the code no longer reads or writes them, and a
half-migrated state (reads on one table, writes on the other) diverges. The
whole run is one transaction with a pre-change backup.

Usage::

    python tools/university/migrate_committee_council_events.py            # dry run
    python tools/university/migrate_committee_council_events.py --apply
    python tools/university/migrate_committee_council_events.py --apply --db /path/to.db
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from education_system import paths  # noqa: E402
from education_system.systems.university.infrastructure.database.schemas.unified_events_link import (  # noqa: E402
    SOURCE_COMMITTEE,
    SOURCE_COMMUNITY,
    SOURCE_STUDENT_COUNCIL,
    ensure_source_link,
    link_source_event,
    start_datetime,
)

LEGACY = ("public_events", "sc_events", "committee_meetings")
CHILDREN = ("committee_agenda_items", "committee_votes")
_FK_TO_MEETINGS = re.compile(
    r"REFERENCES\s+\"?committee_meetings\"?\s*\(\s*\"?\w+\"?\s*\)", re.I)


def _table_exists(conn, name) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _rows(conn, table):
    if not _table_exists(conn, table):
        return []
    # db-audit: ignore[DBW001] - table comes from the LEGACY/CHILDREN literals
    return conn.execute(f'SELECT * FROM "{table}"').fetchall()


def _get(row, key):
    return row[key] if key in row.keys() else None


def _public_fields(r):
    return {
        "title": _get(r, "event_name") or "(untitled)",
        "organizer_id": _get(r, "organizer_id"),
        "event_date": _get(r, "event_date"),
        "start_datetime": start_datetime(_get(r, "event_date")),
        "location": _get(r, "location"),
        "description": _get(r, "description"),
        "max_capacity": _get(r, "expected_attendance"),
        "status": _get(r, "status") or "planned",
        "created_at": _get(r, "created_at"),
    }


def _council_fields(r):
    cal = _get(r, "calendar_event_id")
    return {
        "title": _get(r, "name") or "(untitled)",
        "event_date": _get(r, "event_date"),
        "start_time": _get(r, "event_time") or None,
        "start_datetime": start_datetime(_get(r, "event_date"), _get(r, "event_time")),
        "location": _get(r, "venue"),
        "organizer_name": _get(r, "organiser"),
        "description": _get(r, "description"),
        "notes": f"academic calendar entry {cal}" if cal else None,
        "created_at": _get(r, "created_at"),
    }


def _meeting_fields(r):
    return {
        "event_category": "committee_meeting",
        "committee_id": _get(r, "committee_id"),
        "title": _get(r, "title") or "(untitled)",
        "event_date": _get(r, "meeting_date"),
        "start_time": _get(r, "start_time"),
        "end_time": _get(r, "end_time"),
        "start_datetime": start_datetime(_get(r, "meeting_date"), _get(r, "start_time")),
        "location": _get(r, "location"),
        "virtual_link": _get(r, "virtual_link"),
        "status": _get(r, "status") or "scheduled",
        "organizer_id": _get(r, "chair_id"),
        "secretary_id": _get(r, "secretary_id"),
        "recurrence": _get(r, "recurrence"),
        "notes": _get(r, "notes"),
        "created_by": _get(r, "created_by"),
        "created_at": _get(r, "created_at"),
        "updated_at": _get(r, "updated_at"),
    }


def _meeting_pk(row):
    return _get(row, "meeting_id") if "meeting_id" in row.keys() else _get(row, "id")


def _rebuild_child(conn, table, id_map):
    """Recreate *table* with its meeting FK on unified_events, remapping ids."""
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()[0]
    if not _FK_TO_MEETINGS.search(sql):
        return 0
    index_sql = [r[0] for r in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? "
        "AND sql IS NOT NULL", (table,))]
    rows = _rows(conn, table)
    cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]

    new = f"{table}__new"
    new_sql = _FK_TO_MEETINGS.sub("REFERENCES unified_events(event_id)", sql)
    new_sql = re.sub(r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?\"?%s\"?" % table,
                     f'CREATE TABLE "{new}"', new_sql, count=1, flags=re.I)
    conn.execute(new_sql)

    col_list = ", ".join(f'"{c}"' for c in cols)
    marks = ", ".join("?" for _ in cols)
    at = cols.index("meeting_id")
    for row in rows:
        values = list(row)
        if values[at] not in id_map:
            raise RuntimeError(
                f"{table} row {values[0]} points at meeting {values[at]}, "
                "which has no migrated meeting")
        values[at] = id_map[values[at]]
        conn.execute(f'INSERT INTO "{new}" ({col_list}) VALUES ({marks})', values)

    conn.execute(f'DROP TABLE "{table}"')
    conn.execute(f'ALTER TABLE "{new}" RENAME TO "{table}"')
    for stmt in index_sql:
        conn.execute(stmt)
    return len(rows)


def migrate(db_path, apply=False, backup=True):
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        present = [t for t in LEGACY if _table_exists(conn, t)]
        print(f"database: {db_path}")
        for t in LEGACY + CHILDREN:
            label = f"{len(_rows(conn, t))} row(s)" if _table_exists(conn, t) else "absent"
            print(f"  {t:<24} {label}")

        if not present:
            print("\nNo legacy tables — nothing to migrate.")
            return 0
        if not apply:
            print("\nDry run. Re-run with --apply to migrate and drop "
                  f"{', '.join(present)}.")
            return 0

        if backup:
            dest = paths.maintenance_backup_dir(
                "committee-council-public-events-migration", create=True)
            conn.execute("PRAGMA wal_checkpoint(FULL)")
            shutil.copy2(db_path, dest / Path(db_path).name)
            print(f"\nbackup: {dest / Path(db_path).name}")

        # Must be set outside a transaction; the rebuild drops a parent table.
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN")
        try:
            ensure_source_link(conn)
            moved = {}
            for table, source, fields, pk in (
                ("public_events", SOURCE_COMMUNITY, _public_fields, lambda r: r["event_id"]),
                ("sc_events", SOURCE_STUDENT_COUNCIL, _council_fields, lambda r: r["id"]),
                ("committee_meetings", SOURCE_COMMITTEE, _meeting_fields, _meeting_pk),
            ):
                id_map = {}
                for row in _rows(conn, table):
                    id_map[pk(row)] = link_source_event(
                        conn, source, f"{table}:{pk(row)}", fields(row))
                moved[table] = id_map

            rebuilt = {t: _rebuild_child(conn, t, moved["committee_meetings"])
                       for t in CHILDREN if _table_exists(conn, t)}

            for table in present:
                conn.execute(f'DROP TABLE "{table}"')

            problems = conn.execute("PRAGMA foreign_key_check").fetchall()
            problems = [p for p in problems if p[0] in CHILDREN]
            if problems:
                raise RuntimeError(f"foreign key check failed: {problems}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.execute("PRAGMA foreign_keys = ON")

        for table, id_map in moved.items():
            print(f"  {table:<24} {len(id_map)} row(s) -> unified_events")
        for table, n in rebuilt.items():
            print(f"  {table:<24} rebuilt, {n} row(s), FK -> unified_events")
        print(f"\nDropped: {', '.join(present)}")
        return 0
    finally:
        conn.close()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", default=None, help="database to migrate")
    p.add_argument("--apply", action="store_true", help="write the changes")
    p.add_argument("--no-backup", action="store_true", help="skip the backup")
    args = p.parse_args(argv)
    db = args.db or paths.UNIVERSITY_DEFAULT_DB_PATH
    return migrate(db, apply=args.apply, backup=not args.no_backup)


if __name__ == "__main__":
    raise SystemExit(main())
