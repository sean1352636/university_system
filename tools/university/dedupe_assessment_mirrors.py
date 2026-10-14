#!/usr/bin/env python3
"""Remove copied assessment/assignment/exam rows that duplicate each other.

One piece of work can exist in up to four tables, because three syncs copy
rows between them and none of the copies records where it came from:

    exams ──sync_from_exams──▶ assessments ──sync_assessment_to_assignment──▶ assignments
      └────sync_from_scheduler────▶ exam_portal_exams

The Assessments/Exams view and the student View Grades window now merge these
back into one row each, so the duplication is no longer visible. This script
removes the copies themselves.

Three categories, and they are *not* equally safe:

  assessments   copies of a scheduled exam (``exam_id`` set).
                Safe: the button that made them has been removed, so they do
                not come back. Cleaned by default.

  portal-exams  ``exam_portal_exams`` rows mirroring a scheduled exam.
                ``ExamPortalService.sync_from_scheduler`` still runs whenever
                the Scheduling view is opened, so these WILL be recreated.
                Opt in with --portal-exams.

  assignments   ``assignments`` rows mirroring an assessment.
                ``AssessmentAssignmentService.sync_assessment_to_assignment``
                still runs, so these WILL be recreated. Opt in with
                --assignments.

Nothing referenced by another row is ever deleted: every foreign key pointing
at a candidate is checked first, and a referenced row is reported and skipped.
Foreign keys are enforced in this database, so a blind delete would fail
anyway — this reports *why* instead.

Read-only by default. Pass --apply to write, which takes a backup first.

    python tools/university/dedupe_assessment_mirrors.py            # dry run
    python tools/university/dedupe_assessment_mirrors.py --apply
    python tools/university/dedupe_assessment_mirrors.py --apply --portal-exams
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path


def _paths():
    from education_system import paths
    return paths


def _connect(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def referencing_tables(conn, target_table):
    """Every ``(table, column, target_column)`` with a FK to *target_table*."""
    out = []
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    for name in tables:
        try:
            for fk in conn.execute(f"PRAGMA foreign_key_list('{name}')"):
                if fk[2] == target_table:
                    out.append((name, fk[3], fk[4]))
        except sqlite3.Error:
            continue
    return out


def blockers(conn, target_table, key_column, key_value):
    """Rows elsewhere that point at this one, as ``[(table, count)]``."""
    found = []
    for table, column, target_column in referencing_tables(conn, target_table):
        if target_column != key_column:
            continue
        try:
            # db-audit: ignore[DBW001] - identifiers come from PRAGMA, not input
            n = conn.execute(
                f"SELECT COUNT(*) FROM \"{table}\" WHERE \"{column}\" = ?",
                (key_value,)).fetchone()[0]
        except sqlite3.Error:
            continue
        if n:
            found.append((table, n))
    return found


def find_exam_derived_assessments(conn):
    """assessments rows created from a scheduled exam."""
    return conn.execute(
        "SELECT assessment_id, assessment_name, module_code, exam_id "
        "FROM assessments WHERE exam_id IS NOT NULL").fetchall()


def find_mirrored_portal_exams(conn):
    """exam_portal_exams rows matching a scheduled exam on module + date.

    The same comparison ``sync_from_scheduler`` used to create them.
    """
    try:
        return conn.execute("""
            SELECT pe.id, pe.title, pe.module_code, se.id
            FROM exam_portal_exams pe
            JOIN exams se ON se.module_code = pe.module_code
                         AND se.date = substr(COALESCE(pe.start_time, ''), 1, 10)
        """).fetchall()
    except sqlite3.Error:
        return []


def find_mirrored_assignments(conn):
    """assignments rows matching an assessment on module + title + due date."""
    try:
        return conn.execute("""
            SELECT a.id, a.title, a.module_code, s.assessment_id
            FROM assignments a
            JOIN assessments s
              ON s.module_code = a.module_code
             AND LOWER(TRIM(s.assessment_name)) = LOWER(TRIM(a.title))
             AND substr(COALESCE(s.due_date, ''), 1, 10)
                 = substr(COALESCE(a.due_date, ''), 1, 10)
        """).fetchall()
    except sqlite3.Error:
        return []


CATEGORIES = {
    "assessments": {
        "table": "assessments",
        "key": "assessment_id",
        "find": find_exam_derived_assessments,
        "label": "assessments copied from a scheduled exam",
        "recreated_by": None,
    },
    "portal-exams": {
        "table": "exam_portal_exams",
        "key": "id",
        "find": find_mirrored_portal_exams,
        "label": "portal exams mirroring a scheduled exam",
        "recreated_by": "ExamPortalService.sync_from_scheduler",
    },
    "assignments": {
        "table": "assignments",
        "key": "id",
        "find": find_mirrored_assignments,
        "label": "assignments mirroring an assessment",
        "recreated_by": "AssessmentAssignmentService.sync_assessment_to_assignment",
    },
}


def plan(conn, wanted):
    """Return ``{category: (deletable, skipped)}``."""
    result = {}
    for name in wanted:
        spec = CATEGORIES[name]
        deletable, skipped = [], []
        for row in spec["find"](conn):
            key = row[0]
            held = blockers(conn, spec["table"], spec["key"], key)
            (skipped if held else deletable).append((row, held))
        result[name] = (deletable, skipped)
    return result


def report(result):
    total = 0
    for name, (deletable, skipped) in result.items():
        spec = CATEGORIES[name]
        print(f"\n{spec['label']}")
        print("  " + "-" * 62)
        if spec["recreated_by"]:
            print(f"  NOTE: still recreated by {spec['recreated_by']}")
        if not deletable and not skipped:
            print("  nothing found")
            continue
        for row, _ in deletable:
            print(f"  DELETE  {spec['table']}#{row[0]}  {row[1]}  [{row[2]}]")
        for row, held in skipped:
            why = ", ".join(f"{t} x{n}" for t, n in held)
            print(f"  KEEP    {spec['table']}#{row[0]}  {row[1]}  "
                  f"[{row[2]}] — referenced by {why}")
        total += len(deletable)
    return total


def backup(db_path):
    paths = _paths()
    target_dir = paths.maintenance_backup_dir("assessment-mirror-cleanup",
                                              create=True)
    target = Path(target_dir) / Path(db_path).name
    shutil.copy2(db_path, target)
    print(f"\nbackup: {target}")
    return target


def apply(conn, result):
    removed = 0
    for name, (deletable, _skipped) in result.items():
        spec = CATEGORIES[name]
        for row, _ in deletable:
            # db-audit: ignore[DBW001] - identifiers come from CATEGORIES
            conn.execute(
                f"DELETE FROM \"{spec['table']}\" WHERE \"{spec['key']}\" = ?",
                (row[0],))
            removed += 1
    conn.commit()
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true",
                        help="perform the deletions (default: report only)")
    parser.add_argument("--portal-exams", action="store_true",
                        help="also remove mirrored exam_portal_exams rows "
                             "(they will be recreated by the portal sync)")
    parser.add_argument("--assignments", action="store_true",
                        help="also remove mirrored assignments rows "
                             "(they will be recreated by the assignment sync)")
    parser.add_argument("--db", default=None, help="database path override")
    args = parser.parse_args()

    db_path = args.db or str(_paths().UNIVERSITY_DEFAULT_DB_PATH)
    wanted = ["assessments"]
    if args.portal_exams:
        wanted.append("portal-exams")
    if args.assignments:
        wanted.append("assignments")

    print(f"database: {db_path}")
    conn = _connect(db_path)
    try:
        result = plan(conn, wanted)
        deletable = report(result)

        if not args.apply:
            print(f"\nDry run. {deletable} row(s) would be deleted. "
                  f"Use --apply to perform them.")
            return 0
        if not deletable:
            print("\nNothing to delete.")
            return 0

        backup(db_path)
        removed = apply(conn, result)
        print(f"\n✅ Deleted {removed} duplicate row(s).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
