#!/usr/bin/env python3
"""Migrate ``academic_calendar_events`` into ``unified_events``.

Additive and idempotent: rows are copied into ``unified_events`` tagged
``source_type = 'academic_calendar'`` with ``source_event_id`` holding the
original TEXT ``id``. The legacy table is left untouched and remains
authoritative until the calling code is cut over.

Every column maps **1:1**. That is deliberate: ``date_start``/``date_end`` hold
three different formats across the live rows — a plain date, an ISO
``2026-08-08T09:00:00`` timestamp and a space-separated ``2026-07-22 09:00`` —
so any attempt to parse them into a datetime plus a separate time silently
corrupts one of the three. ``date`` is also a distinct fact from ``date_start``
(they differ on 787 of 810 rows), which is why ``event_date`` exists separately.

Usage::

    python tools/university/migrate_calendar_events.py            # dry run
    python tools/university/migrate_calendar_events.py --apply
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
    ensure_source_link, link_source_event,
)

SOURCE = "academic_calendar"

#: legacy column -> unified column. Anything absent is stored under its own name.
FIELDS = {
    "name": "title", "date": "event_date", "date_start": "start_datetime",
    "date_end": "end_datetime", "date_added": "created_at",
    "last_modified": "updated_at", "organizer": "organizer_name",
}
PASSTHROUGH = ["description", "event_type", "created_by", "start_time", "end_time",
               "location", "audience", "assignment_id", "trip_id", "participants",
               "status", "country_code", "region", "is_active"]

LEGACY_COLUMNS = ["id", "name", "date", "date_start", "date_end", "description",
                  "event_type", "date_added", "last_modified", "created_by",
                  "start_time", "end_time", "location", "audience", "assignment_id",
                  "trip_id", "organizer", "participants", "status", "country_code",
                  "region", "is_active"]


def migrate(db_path, apply=False, backup=True):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM academic_calendar_events ORDER BY id")]
        already = conn.execute(
            "SELECT COUNT(*) FROM unified_events WHERE source_type = ?",
            (SOURCE,)).fetchone()[0]
        print(f"database: {db_path}")
        print(f"  academic_calendar_events   {len(rows)} row(s)")
        print(f"  already in unified_events  {already} row(s)")
        if not apply:
            print(f"\nDry run. {len(rows)} row(s) would be migrated. Use --apply.")
            return 0

        if backup:
            dest = paths.maintenance_backup_dir("calendar-events-migration", create=True)
            conn.execute("PRAGMA wal_checkpoint(FULL)")
            shutil.copy2(db_path, dest / Path(db_path).name)
            print(f"\nbackup: {dest / Path(db_path).name}")

        with conn:
            ensure_source_link(conn)
            for r in rows:
                payload = {u: r.get(l) for l, u in FIELDS.items()}
                payload.update({c: r.get(c) for c in PASSTHROUGH})
                link_source_event(conn, SOURCE, r["id"], payload)

        migrated = conn.execute(
            "SELECT COUNT(*) FROM unified_events WHERE source_type = ?",
            (SOURCE,)).fetchone()[0]
        print(f"\n  migrated: {migrated} row(s)")

        # fidelity: every legacy column, every row, read back from unified
        back = {r["source_event_id"]: r for r in conn.execute(
            "SELECT * FROM unified_events WHERE source_type = ?", (SOURCE,))}
        bad = []
        for r in rows:
            u = back.get(r["id"])
            if u is None:
                bad.append((r["id"], "MISSING", None, None)); continue
            for legacy in LEGACY_COLUMNS:
                if legacy == "id":
                    got = u["source_event_id"]
                else:
                    got = u[FIELDS.get(legacy, legacy)]
                if r.get(legacy) != got:
                    bad.append((r["id"], legacy, r.get(legacy), got))
        print(f"  fidelity: {len(rows)} rows x {len(LEGACY_COLUMNS)} cols, "
              f"{len(bad)} mismatch(es)")
        for b in bad[:8]:
            print("     ", b)
        print("\nLegacy table left in place and unchanged.")
        return 1 if bad else 0
    finally:
        conn.close()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", default=None)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--no-backup", action="store_true")
    a = p.parse_args(argv)
    return migrate(a.db or paths.UNIVERSITY_DEFAULT_DB_PATH, a.apply, not a.no_backup)


if __name__ == "__main__":
    raise SystemExit(main())
