#!/usr/bin/env python3
"""Remove the sample residences that ``init_housing_db()`` used to invent.

Until 2026-10-30, opening Housing on a database with no buildings inserted
four US-style halls and a grid of rooms with random room types, random
occupancy and random rent (400-1200):

    B001  University Residence Hall   123 Campus Drive     North Campus  4 floors x 10
    B002  Graduate Housing Complex    456 Scholar Avenue   South Campus  3 floors x 8
    B003  Freshman Dormitory          789 College Road     East Campus   5 floors x 15
    B004  International House         321 Global Street    West Campus   2 floors x 10

plus an ``Approved`` application for ``S12345`` preferring B001 (and, when a
free Single was found, an assignment and a "Leaking faucet" maintenance
request). The seed is gone from the code; this script removes what it left in
an existing database.

What is matched
---------------
Only rows carrying the seed's exact fingerprint: the four building ids **with**
their seeded name, address and campus; rooms whose id is in that building's
seeded floor/room grid **and** whose ``created_at`` equals the building's seed
timestamp; and the S12345 application created at that same timestamp. A
building that has been renamed or re-addressed is treated as real and left
alone.

What blocks it
--------------
Before deleting anything, every ``housing_*`` table is scanned for columns
ending in ``room_id`` / ``building_id`` that point at a target, plus the
tables with foreign keys to the facilities ``buildings`` mirror. Any reference
other than the seeded application - an assignment, another application, an
inspection, inventory, a maintenance request, a waitlist entry - **stops the
run** and lists what was found. Pass ``--skip-referenced`` to remove only the
unreferenced seeded rooms instead, keeping each referenced room and its
building.

Safety
------
* Report only unless ``--apply`` is given.
* ``--apply`` takes an online SQLite backup first, to
  ``var/backups/maintenance/remove-seeded-housing/<timestamp>/`` via
  ``maintenance_backup_dir()``, then deletes in one transaction and rolls
  back if the delete would introduce any new foreign key violation.

Usage
-----
    python tools/university/remove_seeded_housing.py                     # report
    python tools/university/remove_seeded_housing.py --apply             # delete
    python tools/university/remove_seeded_housing.py --apply --skip-referenced
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from education_system.paths import (  # noqa: E402
    UNIVERSITY_DEFAULT_DB_PATH,
    maintenance_backup_dir,
)

BACKUP_LABEL = "remove-seeded-housing"

#: building_id -> (name, address, campus, floors, rooms_per_floor), exactly as seeded.
SEEDED_BUILDINGS = {
    "B001": ("University Residence Hall", "123 Campus Drive", "North Campus", 4, 10),
    "B002": ("Graduate Housing Complex", "456 Scholar Avenue", "South Campus", 3, 8),
    "B003": ("Freshman Dormitory", "789 College Road", "East Campus", 5, 15),
    "B004": ("International House", "321 Global Street", "West Campus", 2, 10),
}

SEED_STUDENT = "S12345"


def seeded_room_ids(building_id: str) -> set[str]:
    _, _, _, floors, per_floor = SEEDED_BUILDINGS[building_id]
    return {
        f"{building_id}-{floor}{str(num).zfill(2)}"
        for floor in range(1, floors + 1)
        for num in range(1, per_floor + 1)
    }


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def find_targets(conn) -> tuple[dict[str, str], set[str], set[str]]:
    """Return ``(buildings {id: seed timestamp}, room ids, seeded application ids)``."""
    buildings: dict[str, str] = {}
    for bid, (name, address, campus, _, _) in SEEDED_BUILDINGS.items():
        row = conn.execute(
            "SELECT created_at FROM housing_buildings WHERE building_id = ? "
            "AND building_name = ? AND address = ? AND campus_location = ?",
            (bid, name, address, campus)).fetchone()
        if row:
            buildings[bid] = row["created_at"]

    rooms: set[str] = set()
    for bid, stamp in buildings.items():
        grid = seeded_room_ids(bid)
        for row in conn.execute(
                "SELECT room_id FROM housing_rooms WHERE building_id = ? AND created_at = ?",
                (bid, stamp)):
            if row["room_id"] in grid:
                rooms.add(row["room_id"])

    applications: set[str] = set()
    if "B001" in buildings:
        for row in conn.execute(
                "SELECT application_id FROM housing_applications "
                "WHERE student_id = ? AND preferred_building_id = 'B001' "
                "AND created_at = ? AND status = 'Approved'",
                (SEED_STUDENT, buildings["B001"])):
            applications.add(row["application_id"])
    return buildings, rooms, applications


def _in(values) -> tuple[str, list]:
    values = sorted(values)
    return ",".join("?" * len(values)), values


def scan_references(conn, buildings, rooms, seeded_apps) -> list[dict]:
    """Every row outside the seed set that points at a target building or room."""
    found: list[dict] = []
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'housing%'")]
    for table in tables:
        if table in ("housing_buildings",):
            continue
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]
        for col in cols:
            low = col.lower()
            if low.endswith("room_id"):
                targets = rooms
            elif low.endswith("building_id"):
                targets = set(buildings)
            else:
                continue
            if not targets:
                continue
            if table == "housing_rooms" and low in ("room_id", "building_id"):
                continue
            ph, params = _in(targets)
            key_col = cols[0]
            # db-audit: ignore[DBW001] - table/column names come from sqlite_master/PRAGMA
            sql = (f'SELECT "{key_col}" AS row_key, "{col}" AS target FROM "{table}" '
                   f'WHERE "{col}" IN ({ph})')
            for row in conn.execute(sql, params):
                if table == "housing_applications" and row["row_key"] in seeded_apps:
                    continue
                found.append({"table": table, "column": col,
                              "row": row["row_key"], "target": row["target"]})

    # Seeded applications must not themselves be in use (an assignment or a
    # waitlist entry hanging off them makes them real).
    if seeded_apps:
        ph, params = _in(seeded_apps)
        for table in ("housing_assignments", "housing_waitlist"):
            try:
                # db-audit: ignore[DBW001] - literal table names
                for row in conn.execute(
                        f'SELECT rowid AS row_key, application_id FROM "{table}" '
                        f'WHERE application_id IN ({ph})', params):
                    found.append({"table": table, "column": "application_id",
                                  "row": row["row_key"], "target": row["application_id"]})
            except sqlite3.OperationalError:
                pass

    # Facilities rows hanging off the buildings mirror (energy, assets, ...).
    if buildings:
        ph, params = _in(buildings)
        mirror_ids = [r[0] for r in conn.execute(
            f"SELECT building_id FROM buildings WHERE building_code IN ({ph}) "
            "AND building_type = 'Residence'", params)] if _table_exists(conn, "buildings") else []
        if mirror_ids:
            code_of = dict(conn.execute(
                f"SELECT building_id, building_code FROM buildings WHERE building_id IN "
                f"({','.join('?' * len(mirror_ids))})", mirror_ids).fetchall())
            fk_rows = conn.execute(
                "SELECT m.name, p.\"from\" FROM sqlite_master m, pragma_foreign_key_list(m.name) p "
                "WHERE m.type = 'table' AND p.\"table\" = 'buildings'").fetchall()
            for table, col in fk_rows:
                mph = ",".join("?" * len(mirror_ids))
                # db-audit: ignore[DBW001] - names come from sqlite_master/PRAGMA
                for row in conn.execute(
                        f'SELECT rowid AS row_key, "{col}" AS target FROM "{table}" '
                        f'WHERE "{col}" IN ({mph})', mirror_ids):
                    found.append({"table": table, "column": col, "row": row["row_key"],
                                  "target": code_of.get(row["target"], row["target"])})
    return found


def _table_exists(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (name,)).fetchone() is not None


def _fk_violations(conn) -> set[tuple]:
    return {tuple(row) for row in conn.execute("PRAGMA foreign_key_check")}


def delete(conn, buildings, rooms, applications) -> dict[str, int]:
    removed: dict[str, int] = {}
    baseline = _fk_violations(conn)
    conn.execute("BEGIN IMMEDIATE")
    try:
        if applications:
            ph, params = _in(applications)
            cur = conn.execute(
                f"DELETE FROM housing_applications WHERE application_id IN ({ph})", params)
            removed["housing_applications"] = cur.rowcount
        if rooms:
            ph, params = _in(rooms)
            cur = conn.execute(f"DELETE FROM housing_rooms WHERE room_id IN ({ph})", params)
            removed["housing_rooms"] = cur.rowcount
        if buildings:
            ph, params = _in(buildings)
            # The housing_buildings_mirror_delete trigger removes the matching
            # 'Residence' rows from the facilities `buildings` table.
            cur = conn.execute(
                f"DELETE FROM housing_buildings WHERE building_id IN ({ph})", params)
            removed["housing_buildings"] = cur.rowcount
        # A seeded building kept by --skip-referenced has lost most of its
        # rooms; recount its counters from what is left.
        for bid in SEEDED_BUILDINGS:
            if bid in buildings:
                continue
            conn.execute(
                "UPDATE housing_buildings SET "
                "total_rooms = (SELECT COUNT(*) FROM housing_rooms WHERE building_id = ?), "
                "available_rooms = (SELECT COUNT(*) FROM housing_rooms "
                "                   WHERE building_id = ? AND status = 'Available') "
                "WHERE building_id = ?", (bid, bid, bid))
        introduced = _fk_violations(conn) - baseline
        if introduced:
            raise RuntimeError(
                f"the delete would introduce {len(introduced)} foreign key violation(s): "
                f"{sorted(introduced)[:5]} - nothing was deleted")
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.DatabaseError:
            pass
        raise
    return removed


def backup(conn, db_path: str) -> Path:
    """Online backup (safe with WAL) into the maintenance backup tree."""
    target_dir = maintenance_backup_dir(BACKUP_LABEL, create=True)
    target = target_dir / Path(db_path).name
    dest = sqlite3.connect(str(target))
    try:
        conn.backup(dest)
    finally:
        dest.close()
    return target


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove the sample housing buildings/rooms seeded by init_housing_db().")
    parser.add_argument("--apply", action="store_true",
                        help="back up, then delete (default: report only)")
    parser.add_argument("--skip-referenced", action="store_true",
                        help="keep referenced rooms (and their buildings) instead of refusing")
    parser.add_argument("--db", default=str(UNIVERSITY_DEFAULT_DB_PATH))
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"No such database: {args.db}")
        return 1

    conn = connect(args.db)
    try:
        if not _table_exists(conn, "housing_buildings"):
            print("No housing tables in this database - nothing to do.")
            return 0

        buildings, rooms, applications = find_targets(conn)
        print(f"\nDatabase: {args.db}")
        print(f"Seeded buildings found: {len(buildings)} of {len(SEEDED_BUILDINGS)}")
        for bid in sorted(buildings):
            in_bld = sum(1 for r in rooms if r.startswith(bid + "-"))
            print(f"   {bid}  {SEEDED_BUILDINGS[bid][0]:<28} {in_bld} seeded room(s)")
        print(f"Seeded rooms found: {len(rooms)}")
        print(f"Seeded S12345 application(s): {', '.join(sorted(applications)) or 'none'}")
        if not buildings:
            print("\nNothing to remove.")
            return 0

        refs = scan_references(conn, buildings, rooms, applications)
        if refs:
            print(f"\n{len(refs)} reference(s) to seeded rows found:")
            for ref in refs:
                print(f"   {ref['table']}.{ref['column']} -> {ref['target']}  (row {ref['row']})")

            if not args.skip_referenced:
                print("\nREFUSED: the rows above use seeded buildings/rooms. Re-home or delete "
                      "them first, or run with --skip-referenced to keep those rooms and "
                      "their buildings and remove the rest.")
                return 2

            # Keep each referenced room; keep a building if it is referenced
            # itself or still has a kept room.
            kept_rooms = {r["target"] for r in refs if r["target"] in rooms}
            kept_buildings = {r["target"] for r in refs if r["target"] in buildings}
            kept_buildings |= {rid.split("-", 1)[0] for rid in kept_rooms}
            rooms = rooms - kept_rooms
            buildings = {b: s for b, s in buildings.items() if b not in kept_buildings}
            # The seeded application goes only with B001, and only if nothing
            # hangs off it.
            if "B001" not in buildings or any(r["target"] in applications for r in refs):
                applications = set()
            print(f"\n--skip-referenced: keeping {len(kept_rooms)} room(s) "
                  f"({', '.join(sorted(kept_rooms)) or 'none'}) and building(s) "
                  f"{', '.join(sorted(kept_buildings)) or 'none'}.")

        # A non-seeded room inside a seeded building means staff have started
        # using it: that building is real.
        if buildings:
            ph, params = _in(buildings)
            rph, rparams = _in(rooms) if rooms else ("''", [])
            # db-audit: ignore[DBW001] - placeholder joins only
            leftover = conn.execute(
                f"SELECT COUNT(*) FROM housing_rooms WHERE building_id IN ({ph}) "
                f"AND room_id NOT IN ({rph})", params + rparams).fetchone()[0]
            if leftover:
                print(f"\nREFUSED: {leftover} non-seeded room(s) live in seeded buildings, "
                      "so those buildings are in real use. Nothing was deleted.")
                return 2

        print(f"\nWill delete: {len(buildings)} building(s), {len(rooms)} room(s), "
              f"{len(applications)} application(s).")
        if not args.apply:
            print("Report only. Re-run with --apply to back up and delete.")
            return 0

        path = backup(conn, args.db)
        print(f"Backup written: {path}")
        removed = delete(conn, set(buildings), rooms, applications)
        print("Deleted: " + ", ".join(f"{t} {n}" for t, n in removed.items()))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
