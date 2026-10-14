#!/usr/bin/env python3
"""Attribute taught modules to the courses (programmes) that teach them.

Occupancy, capacity and every course-level report reach a module through
``services.bus.course_bridge``, which maps courses to modules via
``course_curriculum``, ``course_module_map`` and ``modules.course``. A module
in none of them belongs to no course, so its enrolments are attributed to
nothing and simply vanish from course reporting.

This tool finds those modules, infers a course where the *data* supports it,
and writes the link to ``course_module_map`` (the link table the Course ⇄
Module Links tab uses), stamped with the evidence in ``link_source``.

Evidence, in order of preference:

1. ``modules.department`` naming a course code — the CIS catalogue uses
   'CS', 'DS' and 'both' (shared teaching), which maps directly.
2. The programmes of the students actually enrolled: if every enrolled
   student on a module is registered on one course, that is the course.

A module with neither is **left alone and reported**. Guessing from a code
prefix would put invented rows into a real curriculum, and the modules that
lack evidence here are placeholders (zero credits, auto-generated
"Module X" names, no enrolments) that want deleting rather than mapping.

Usage
-----
    python tools/university/map_unmapped_modules.py             # report only
    python tools/university/map_unmapped_modules.py --apply     # write links
    python tools/university/map_unmapped_modules.py --db PATH   # another DB

``--apply`` backs the database up first (var/backups/maintenance/...) and is
idempotent: ``course_module_map`` is UNIQUE on (course_code, module_code), so
re-running adds nothing.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from education_system.paths import (  # noqa: E402
    UNIVERSITY_DEFAULT_DB_PATH,
    maintenance_backup_dir,
)

#: ``modules.department`` values that mean "taught on more than one course".
SHARED_MARKERS = {"both", "shared", "common", "all"}


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def course_codes(conn) -> dict[str, str]:
    """``UPPER(code) -> code`` for every course, plus name lookups."""
    out: dict[str, str] = {}
    for row in conn.execute(
        "SELECT COALESCE(NULLIF(TRIM(course_code), ''), code) AS code, "
        "COALESCE(NULLIF(TRIM(course_name), ''), name) AS name FROM courses"
    ):
        if row["code"]:
            out[row["code"].strip().upper()] = row["code"].strip()
            if row["name"]:
                out.setdefault(row["name"].strip().upper(), row["code"].strip())
    return out


def unmapped_modules(conn) -> list[sqlite3.Row]:
    """Modules that no mapping source attributes to a course."""
    return conn.execute(
        """
        SELECT m.module_code, m.module_name, m.department, m.credits
          FROM modules m
         WHERE COALESCE(TRIM(m.module_code), '') <> ''
           AND COALESCE(TRIM(m.course), '') = ''
           AND NOT EXISTS (SELECT 1 FROM course_curriculum cc
                            WHERE TRIM(cc.module_code) = TRIM(m.module_code))
           AND NOT EXISTS (SELECT 1 FROM course_module_map cm
                            WHERE TRIM(cm.module_code) = TRIM(m.module_code))
         ORDER BY m.module_code
        """
    ).fetchall()


def enrolled_programmes(conn) -> dict[str, dict[str, int]]:
    """``module_code -> {course_code: student count}`` from live enrolments."""
    out: dict[str, dict[str, int]] = defaultdict(dict)
    rows = conn.execute(
        """
        SELECT sm.module_code AS module_code, TRIM(s.course) AS course,
               COUNT(DISTINCT sm.student_id) AS n
          FROM student_modules sm
          JOIN students s ON s.student_id = sm.student_id
         WHERE sm.status = 'Enrolled' AND COALESCE(TRIM(s.course), '') <> ''
         GROUP BY sm.module_code, TRIM(s.course)
        """
    ).fetchall()
    codes = course_codes(conn)
    for row in rows:
        resolved = codes.get((row["course"] or "").strip().upper())
        if resolved:
            out[row["module_code"]][resolved] = row["n"]
    return out


def infer(conn) -> tuple[list[dict], list[dict]]:
    """Return ``(proposals, unresolved)`` for every unmapped module."""
    codes = course_codes(conn)
    by_enrolment = enrolled_programmes(conn)
    all_codes = sorted({v for v in codes.values()})

    proposals: list[dict] = []
    unresolved: list[dict] = []

    for module in unmapped_modules(conn):
        code = module["module_code"].strip()
        dept = (module["department"] or "").strip()
        enrolled = by_enrolment.get(code, {})

        if dept and dept.upper() in codes:
            # 1a. Department names a single course.
            target = [codes[dept.upper()]]
            evidence = f"department={dept}"
        elif dept.lower() in SHARED_MARKERS:
            # 1b. Shared teaching: the courses of the students taking it.
            target = sorted(enrolled) or []
            evidence = (f"department={dept}, students on "
                        f"{'+'.join(target)}" if target else f"department={dept}")
        elif len(enrolled) == 1:
            # 2. Every enrolled student is on the same programme.
            target = [next(iter(enrolled))]
            evidence = f"all {sum(enrolled.values())} enrolled students on {target[0]}"
        else:
            target = []
            evidence = ""

        target = [t for t in target if t in all_codes]
        entry = {
            "module_code": code,
            "module_name": module["module_name"],
            "department": dept or None,
            "credits": module["credits"],
            "enrolled": sum(enrolled.values()),
            "courses": target,
            "evidence": evidence,
        }
        (proposals if target else unresolved).append(entry)

    return proposals, unresolved


def apply_links(conn, proposals: list[dict]) -> int:
    """Write the inferred links; returns how many rows were added."""
    added = 0
    for entry in proposals:
        for course in entry["courses"]:
            cur = conn.execute(
                "INSERT OR IGNORE INTO course_module_map "
                "(course_code, module_code, link_source) VALUES (?, ?, ?)",
                (course, entry["module_code"], f"inferred: {entry['evidence']}"),
            )
            added += cur.rowcount if cur.rowcount > 0 else 0
    conn.commit()
    return added


def backup(db_path: str) -> Path:
    target_dir = maintenance_backup_dir("module-course-mapping", create=True)
    target = target_dir / Path(db_path).name
    shutil.copy2(db_path, target)
    return target


def report(proposals: list[dict], unresolved: list[dict]) -> None:
    print(f"\n{len(proposals) + len(unresolved)} module(s) belong to no course\n")

    if proposals:
        print(f"MAPPABLE ({len(proposals)}) — evidence-backed:")
        print(f"  {'module':<10} {'-> course(s)':<14} {'enrol':>5}  evidence")
        for entry in proposals:
            print(f"  {entry['module_code']:<10} "
                  f"{'+'.join(entry['courses']):<14} "
                  f"{entry['enrolled']:>5}  {entry['evidence']}")
            print(f"             {str(entry['module_name'])[:60]}")

    if unresolved:
        print(f"\nNO EVIDENCE ({len(unresolved)}) — left alone:")
        print(f"  {'module':<10} {'credits':>7} {'enrol':>6}  name")
        for entry in unresolved:
            print(f"  {entry['module_code']:<10} {str(entry['credits']):>7} "
                  f"{entry['enrolled']:>6}  {str(entry['module_name'])[:50]}")
        print("\n  These have no department, no enrolments and generated names:"
              "\n  placeholders to delete or assign by hand, not to guess at.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write the inferred links (default: report only)")
    parser.add_argument("--db", default=str(UNIVERSITY_DEFAULT_DB_PATH),
                        help="database to inspect (default: the live one)")
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"No such database: {args.db}")
        return 1

    conn = connect(args.db)
    try:
        proposals, unresolved = infer(conn)
        report(proposals, unresolved)

        if not args.apply:
            if proposals:
                print(f"\nDry run. Re-run with --apply to write "
                      f"{sum(len(p['courses']) for p in proposals)} link(s).")
            return 0

        if not proposals:
            print("\nNothing to apply.")
            return 0

        saved = backup(args.db)
        print(f"\nBacked up to {saved}")
        added = apply_links(conn, proposals)
        print(f"Wrote {added} link(s) to course_module_map.")

        remaining = len(unmapped_modules(conn))
        print(f"Modules still unmapped: {remaining}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
