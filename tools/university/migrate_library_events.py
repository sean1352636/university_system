#!/usr/bin/env python3
"""Move library events into ``unified_events``, keeping provenance.

This is the first slice of the events consolidation. ``library_events`` and
``library_event_attendance`` become rows in ``unified_events`` /
``unified_event_registrations`` tagged ``source_type = 'library'``, with
``source_event_id`` holding the original ``library_events.event_id``.

The link is what makes this safe to re-run: a unique partial index on
``(source_type, source_event_id)`` means a second pass updates the row it
created the first time instead of duplicating it.

Usage::

    python tools/university/migrate_library_events.py            # dry run
    python tools/university/migrate_library_events.py --apply
    python tools/university/migrate_library_events.py --apply --db /path/to.db

The legacy tables are left in place and untouched. Drop them only once you are
satisfied with the migrated data.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from education_system import paths  # noqa: E402
from education_system.systems.university.infrastructure.database.schemas.unified_events_link import (  # noqa: E402
    SOURCE_LIBRARY,
    ensure_source_link,
    link_source_event,
)


def _table_exists(conn, name) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _start_datetime(event_date, event_time):
    date_part = (event_date or "").strip()
    time_part = (event_time or "").strip()
    return f"{date_part} {time_part}".strip() if date_part else (time_part or None)


def migrate(db_path, apply=False, backup=True):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if not _table_exists(conn, "library_events"):
            print("No library_events table — nothing to migrate.")
            return 0

        events = conn.execute("SELECT * FROM library_events").fetchall()
        attendance = []
        if _table_exists(conn, "library_event_attendance"):
            attendance = conn.execute(
                "SELECT * FROM library_event_attendance").fetchall()

        print(f"database: {db_path}")
        print(f"  library_events              {len(events)} row(s)")
        print(f"  library_event_attendance    {len(attendance)} row(s)")

        already = conn.execute(
            "SELECT COUNT(*) FROM unified_events WHERE source_type = ?",
            (SOURCE_LIBRARY,),
        ).fetchone()[0]
        print(f"  already in unified_events   {already} row(s)")

        if not events and not attendance:
            print("\nNothing to migrate.")
            return 0
        if not apply:
            print(f"\nDry run. {len(events)} event(s) and {len(attendance)} "
                  f"registration(s) would be migrated. Re-run with --apply.")
            return 0

        if backup:
            dest = paths.maintenance_backup_dir("library-events-migration", create=True)
            conn.execute("PRAGMA wal_checkpoint(FULL)")
            shutil.copy2(db_path, dest / Path(db_path).name)
            print(f"\nbackup: {dest / Path(db_path).name}")

        id_map = {}
        with conn:
            ensure_source_link(conn)
            for row in events:
                keys = row.keys()
                unified_id = link_source_event(
                    conn, SOURCE_LIBRARY, row["event_id"],
                    {
                        "title": row["event_name"],
                        "description": row["description"] if "description" in keys else None,
                        "start_datetime": _start_datetime(
                            row["event_date"] if "event_date" in keys else None,
                            row["event_time"] if "event_time" in keys else None),
                        "location": row["location"] if "location" in keys else None,
                        "max_capacity": row["max_capacity"] if "max_capacity" in keys else None,
                        "status": (row["status"] if "status" in keys else None) or "scheduled",
                        "created_by": row["created_by"] if "created_by" in keys else None,
                        "created_at": row["created_at"] if "created_at" in keys else None,
                        "event_type": "library",
                    },
                )
                id_map[row["event_id"]] = unified_id

            moved_registrations = 0
            for row in attendance:
                unified_id = id_map.get(row["event_id"])
                if unified_id is None:
                    print(f"  ! registration {row['attendance_id']} points at "
                          f"event {row['event_id']} which has no migrated event; skipped")
                    continue
                keys = row.keys()
                attendee = row["attendee_id"]
                registered_at = row["registered_at"] if "registered_at" in keys else None
                # Re-runnable: skip a registration already carried across.
                exists = conn.execute(
                    "SELECT 1 FROM unified_event_registrations "
                    "WHERE event_id = ? AND user_id = ? AND COALESCE(registered_at,'') = ?",
                    (unified_id, attendee, registered_at or ""),
                ).fetchone()
                if exists:
                    continue
                conn.execute(
                    "INSERT INTO unified_event_registrations "
                    "(event_id, user_id, attendee_name, registered_at, "
                    " registration_date, status) VALUES (?, ?, ?, ?, ?, 'registered')",
                    (unified_id, attendee,
                     row["attendee_name"] if "attendee_name" in keys else None,
                     registered_at, registered_at),
                )
                moved_registrations += 1

        print(f"\n  events migrated/refreshed   {len(id_map)}")
        print(f"  registrations migrated      {moved_registrations}")
        print("\nLegacy tables left in place and unchanged.")
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
