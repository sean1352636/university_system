#!/usr/bin/env python3
"""Remove the placeholder modules left behind by ad-hoc testing.

Nine modules in ``modules`` are debris: zero credits, no year or semester, no
enrolments, and names auto-generated as "Module <code>". They belong to no
course, so they clutter every module picker and the catalogue without ever
being taught.

They are **not** free-standing, which is why this is a script and not a DELETE:
twelve rows in four other tables point at them (textbook records, a
``lesson_courses`` entry, a mitigating-circumstances claim, a curriculum module
descriptor). Those go too, in dependency order.

``CS101`` is deliberately **kept**. It carries a QR attendance session and
record behind ``NO ACTION`` foreign keys — the delete would fail — plus two
course evaluations, an evaluation pulse, an MC claim and a deadline extension.
That is a working feature demo, not debris.

Safety
------
* Re-scans every table in the database for references before touching
  anything, and **aborts** if a reference appears outside the expected set —
  the data may have moved on since this was written.
* ``--apply`` backs the database up first, deletes inside one transaction,
  and runs ``PRAGMA foreign_key_check`` before committing. Any violation
  rolls the whole thing back.

Usage
-----
    python tools/university/delete_placeholder_modules.py           # report
    python tools/university/delete_placeholder_modules.py --apply   # delete
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from education_system.paths import (  # noqa: E402
    UNIVERSITY_DEFAULT_DB_PATH,
    maintenance_backup_dir,
)

#: The placeholder modules to remove.
TARGETS = ["CS-X-101", "CS102", "CS201", "CS301", "DS201",
           "ENG301", "MA101", "MATH201", "WEB101"]

#: Kept on purpose — a live-looking feature demo, not debris.
KEPT = {"CS101": "attendance (FK), evaluations, MC claim, evaluation pulse"}

#: Rows that hang off a *dependent* rather than off the module, deleted first.
#:
#: These are the layer the first run tripped over: an MC claim carries a panel
#: decision and any evidence, and a curriculum module descriptor carries its
#: assessment components. All are ``NO ACTION`` foreign keys, so the parent
#: delete fails outright until they go. Both chains here are fabricated demo
#: data — the MC claim belongs to 'S88888', which is not a student record.
GRANDCHILDREN = [
    ("mc_panel_items", "claim_id",
     "SELECT id FROM mc_claims WHERE module_code IN ({placeholders})"),
    ("mc_evidence", "claim_id",
     "SELECT id FROM mc_claims WHERE module_code IN ({placeholders})"),
    ("mc_deadline_extensions", "claim_id",
     "SELECT id FROM mc_claims WHERE module_code IN ({placeholders})"),
    ("curr_assessment_components", "module_descriptor_id",
     "SELECT id FROM curr_module_descriptors WHERE module_code IN ({placeholders})"),
]

#: Tables whose rows may be removed along with the module, in delete order.
#: Anything referencing a target outside this list stops the run.
DEPENDENTS = [
    ("mc_deadline_extensions", "module_code"),   # child of mc_claims
    ("mc_claims", "module_code"),
    ("textbooks", "module_code"),
    ("lesson_courses", "code"),
    ("curr_module_descriptors", "module_code"),
    ("course_module_map", "module_code"),
    ("course_curriculum", "module_code"),
]

#: Column names that could carry a module code, for the pre-flight scan.
CODE_COLUMNS = ("module_code", "module", "course_code", "code", "subject")


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def scan_references(conn) -> dict[str, int]:
    """``"table.column" -> row count`` for everything pointing at a target."""
    placeholders = ",".join("?" * len(TARGETS))
    found: dict[str, int] = {}
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    for table in tables:
        try:
            columns = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]
        except sqlite3.DatabaseError:
            continue
        for column in columns:
            if column.lower() not in CODE_COLUMNS:
                continue
            try:
                count = conn.execute(
                    f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" IN ({placeholders})',
                    TARGETS,
                ).fetchone()[0]
            except sqlite3.DatabaseError:
                continue
            if count:
                found[f"{table}.{column}"] = count
    return found


def unexpected(found: dict[str, int]) -> dict[str, int]:
    """References this script is not prepared to remove."""
    allowed = {f"{t}.{c}" for t, c in DEPENDENTS} | {"modules.module_code"}
    return {k: v for k, v in found.items() if k not in allowed}


def count_grandchildren(conn) -> dict[str, int]:
    """How many rows hang off the dependents, per table."""
    placeholders = ",".join("?" * len(TARGETS))
    out: dict[str, int] = {}
    for table, column, subquery in GRANDCHILDREN:
        try:
            count = conn.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" IN '
                f'({subquery.format(placeholders=placeholders)})',
                TARGETS,
            ).fetchone()[0]
        except sqlite3.DatabaseError:
            continue
        if count:
            out[table] = count
    return out


def blockers(conn) -> dict[str, int]:
    """Enrolments or grades would make a module real, not debris."""
    placeholders = ",".join("?" * len(TARGETS))
    out = {}
    for table in ("student_modules", "module_grades", "student_grades",
                  "module_enrolments", "assessments", "assignments"):
        try:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE module_code IN ({placeholders})",
                TARGETS,
            ).fetchone()[0]
        except sqlite3.DatabaseError:
            continue
        if count:
            out[table] = count
    return out


def _fk_violations(conn) -> set[tuple]:
    """Every foreign key violation currently in the database."""
    return {tuple(row) for row in conn.execute("PRAGMA foreign_key_check")}


def delete_all(conn) -> dict[str, int]:
    """Delete dependents then modules inside one transaction."""
    placeholders = ",".join("?" * len(TARGETS))
    removed: dict[str, int] = {}
    baseline = _fk_violations(conn)
    conn.execute("BEGIN")
    try:
        for table, column, subquery in GRANDCHILDREN:
            try:
                cur = conn.execute(
                    f'DELETE FROM "{table}" WHERE "{column}" IN '
                    f'({subquery.format(placeholders=placeholders)})',
                    TARGETS,
                )
            except sqlite3.OperationalError:
                continue          # table absent in this database
            if cur.rowcount:
                removed[table] = cur.rowcount

        for table, column in DEPENDENTS:
            try:
                cur = conn.execute(
                    f'DELETE FROM "{table}" WHERE "{column}" IN ({placeholders})',
                    TARGETS,
                )
            except sqlite3.OperationalError:
                continue          # table absent in this database
            if cur.rowcount:
                removed[table] = cur.rowcount

        cur = conn.execute(
            f"DELETE FROM modules WHERE module_code IN ({placeholders})", TARGETS)
        removed["modules"] = cur.rowcount

        # Compare against a baseline, not against zero: this database already
        # carries 9 unrelated orphans (student rows referenced by
        # medical_conditions, module_enrolments and programme_registrations
        # that no longer exist). Only violations *this* delete introduces
        # should roll it back.
        after = _fk_violations(conn)
        introduced = after - baseline
        if introduced:
            conn.execute("ROLLBACK")
            raise RuntimeError(
                f"this delete would introduce {len(introduced)} foreign key "
                f"violation(s): {sorted(introduced)[:5]} — nothing was deleted")
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.DatabaseError:
            pass
        raise
    return removed


def backup(db_path: str) -> Path:
    target_dir = maintenance_backup_dir("placeholder-module-cleanup", create=True)
    target = target_dir / Path(db_path).name
    shutil.copy2(db_path, target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="perform the deletion (default: report only)")
    parser.add_argument("--db", default=str(UNIVERSITY_DEFAULT_DB_PATH))
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"No such database: {args.db}")
        return 1

    conn = connect(args.db)
    try:
        present = [r[0] for r in conn.execute(
            "SELECT module_code FROM modules WHERE module_code IN (%s) ORDER BY module_code"
            % ",".join("?" * len(TARGETS)), TARGETS)]
        print(f"\nTargets present: {len(present)} of {len(TARGETS)}")
        for code in present:
            print(f"   {code}")
        for code, why in KEPT.items():
            print(f"\nKept on purpose: {code} — {why}")

        held = blockers(conn)
        if held:
            print(f"\nABORT: these modules are in use: {held}")
            return 2

        found = scan_references(conn)
        dependents = {k: v for k, v in found.items() if k != "modules.module_code"}
        print(f"\nDependent rows to remove ({sum(dependents.values())}):")
        for ref, count in sorted(dependents.items()):
            print(f"   {ref}: {count}")

        indirect = count_grandchildren(conn)
        if indirect:
            print(f"\nRows hanging off those dependents ({sum(indirect.values())}):")
            for table, count in sorted(indirect.items()):
                print(f"   {table}: {count}")

        strays = unexpected(found)
        if strays:
            print(f"\nABORT: unexpected references {strays}")
            print("Review them before deleting; this script will not guess.")
            return 3

        if not args.apply:
            print("\nDry run. Re-run with --apply to delete.")
            return 0

        saved = backup(args.db)
        print(f"\nBacked up to {saved}")
        removed = delete_all(conn)
        print("Deleted:")
        for table, count in sorted(removed.items()):
            print(f"   {table}: {count}")

        leftover = scan_references(conn)
        print(f"\nRemaining references: {leftover or 'none'}")
        print(f"foreign_key_check: {len(_fk_violations(conn))} violation(s) "
              "(pre-existing orphans, unrelated to this delete)")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
