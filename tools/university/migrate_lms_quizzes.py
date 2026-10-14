#!/usr/bin/env python3
"""Migrate ``lms_quizzes`` into assignments + exam_portal, then drop the tables.

Quizzes now live as ``assignments`` rows with ``assignment_type='quiz'``,
backed by ``exam_portal_exams`` for the questions and the sitting (see
``domain.services.assignments.quiz_service``). This moves whatever the old
``lms_quizzes`` tables hold into that shape and then removes them.

Nothing runs without ``--apply``. A dry run is the default and prints exactly
what would change. ``--apply`` takes a full database copy into
``var/backups/maintenance/lms_quiz_migration/<timestamp>/`` first.

    python -m tools.university.migrate_lms_quizzes            # dry run
    python -m tools.university.migrate_lms_quizzes --apply
    python -m tools.university.migrate_lms_quizzes --apply --keep-tables
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

_LEGACY_TABLES = (
    "lms_quiz_submissions",
    "lms_quiz_attempts",
    "lms_quiz_questions",
    "lms_quizzes",
)


def _resolve_module_code(conn, lms_course_id):
    """The module a legacy quiz belongs to, via its LMS course."""
    row = conn.execute(
        "SELECT module_code FROM lms_courses WHERE lms_course_id = ?",
        (lms_course_id,),
    ).fetchone()
    return row[0] if row else None


def _module_exists(conn, module_code):
    """``assignments.module_code`` is a foreign key onto ``modules``."""
    if not module_code:
        return False
    row = conn.execute(
        "SELECT 1 FROM modules WHERE module_code = ? LIMIT 1", (module_code,)
    ).fetchone()
    return row is not None


def survey(conn):
    """What is there to move, and what stands in the way."""
    rows = conn.execute(
        "SELECT quiz_id, lms_course_id, title, description, duration_minutes, "
        "       passing_score, max_attempts, available_until "
        "FROM lms_quizzes ORDER BY quiz_id"
    ).fetchall()

    plan = []
    for (quiz_id, course_id, title, description, duration,
         passing, attempts, until) in rows:
        module_code = _resolve_module_code(conn, course_id)
        questions = conn.execute(
            "SELECT COUNT(*) FROM lms_quiz_questions WHERE quiz_id = ?", (quiz_id,)
        ).fetchone()[0]
        blocker = None
        if not module_code:
            blocker = f"LMS course {course_id} has no module_code"
        elif not _module_exists(conn, module_code):
            blocker = f"module {module_code!r} is not in the modules table"
        plan.append({
            "quiz_id": quiz_id, "title": title, "module_code": module_code,
            "questions": questions, "duration": duration or 60,
            "passing": passing if passing is not None else 50.0,
            "attempts": attempts or 1, "until": until,
            "description": description or "", "blocker": blocker,
        })
    return plan


def migrate_one(conn, entry, created_by):
    """Write the assignment + exam pair for one legacy quiz. Returns ids."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_marks = conn.execute(
        "SELECT COALESCE(SUM(points), 0) FROM lms_quiz_questions WHERE quiz_id = ?",
        (entry["quiz_id"],),
    ).fetchone()[0] or 100.0

    cursor = conn.execute(
        """INSERT INTO assignments
               (module_code, title, description, due_date, max_marks,
                assignment_type, is_active, created_by, created_at, status,
                duration_minutes, max_score, time_limit)
           VALUES (?, ?, ?, ?, ?, 'quiz', 1, ?, ?, 'active', ?, ?, ?)""",
        (entry["module_code"], entry["title"], entry["description"],
         entry["until"], total_marks, created_by, now,
         entry["duration"], total_marks, entry["duration"]),
    )
    assignment_id = cursor.lastrowid

    cursor = conn.execute(
        """INSERT INTO exam_portal_exams
               (title, description, module_code, created_by, status,
                duration_minutes, pass_mark, total_marks, max_attempts,
                end_time, assignment_id)
           VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?)""",
        (entry["title"], entry["description"], entry["module_code"],
         str(created_by), entry["duration"], entry["passing"], total_marks,
         entry["attempts"], entry["until"], assignment_id),
    )
    exam_id = cursor.lastrowid

    # Carry the questions across. Legacy rows store options as JSON already.
    moved = 0
    for (qtext, qtype, answer, points, options, explanation, order) in conn.execute(
        "SELECT question_text, question_type, correct_answer, points, options, "
        "       explanation, display_order "
        "FROM lms_quiz_questions WHERE quiz_id = ? ORDER BY display_order, question_id",
        (entry["quiz_id"],),
    ).fetchall():
        conn.execute(
            """INSERT INTO exam_portal_questions
                   (exam_id, question_type, question_text, options_json,
                    correct_answer, marks, order_index, explanation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (exam_id, qtype or "short_answer", qtext, options, answer,
             points or 1, order or (moved + 1), explanation),
        )
        moved += 1

    return assignment_id, exam_id, moved


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true",
                        help="actually write; without it this is a dry run")
    parser.add_argument("--keep-tables", action="store_true",
                        help="migrate but leave the lms_quiz* tables in place")
    parser.add_argument("--db", help="database to operate on (default: the live one)")
    parser.add_argument("--created-by", default=None,
                        help="users.id to record as the author (default: first admin)")
    args = parser.parse_args(argv)

    from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH, maintenance_backup_dir
    db_path = Path(args.db) if args.db else Path(UNIVERSITY_DEFAULT_DB_PATH)
    if not db_path.exists():
        print(f"No such database: {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    try:
        plan = survey(conn)
    except sqlite3.OperationalError as exc:
        print(f"Nothing to do: {exc}")
        return 0

    print(f"Database: {db_path}")
    print(f"Legacy quizzes found: {len(plan)}\n")
    for entry in plan:
        state = f"BLOCKED — {entry['blocker']}" if entry["blocker"] else "ready"
        print(f"  quiz {entry['quiz_id']}: {entry['title']!r} "
              f"-> module {entry['module_code']}, {entry['questions']} question(s)  [{state}]")

    movable = [e for e in plan if not e["blocker"]]
    blocked = [e for e in plan if e["blocker"]]
    print(f"\n{len(movable)} to migrate, {len(blocked)} blocked.")

    if not args.apply:
        print("\nDry run — nothing written. Re-run with --apply to make these changes.")
        return 0

    if blocked and not args.keep_tables:
        print("\nRefusing to drop the tables while rows are blocked: fix those first, "
              "or pass --keep-tables.")
        return 2

    created_by = args.created_by
    if created_by is None:
        row = conn.execute(
            "SELECT id FROM users WHERE LOWER(COALESCE(role,'')) = 'admin' "
            "ORDER BY id LIMIT 1").fetchone()
        created_by = row[0] if row else None
    if created_by is None:
        print("No admin user to attribute the migrated quizzes to; pass --created-by.")
        return 2

    backup_dir = maintenance_backup_dir("lms_quiz_migration", create=True)
    backup = backup_dir / db_path.name
    shutil.copy(db_path, backup)
    print(f"\nBackup written to {backup}")

    migrated = 0
    try:
        # exam_portal_exams.assignment_id is added on demand by the service;
        # this runs before any GUI has, so add it here too.
        from education_system.systems.university.domains.academics.domain.services.assignments.quiz_service import (
            ensure_link_column,
        )
        ensure_link_column(conn)

        for entry in movable:
            assignment_id, exam_id, questions = migrate_one(conn, entry, created_by)
            print(f"  quiz {entry['quiz_id']} -> assignment {assignment_id}, "
                  f"exam {exam_id}, {questions} question(s)")
            migrated += 1

        if not args.keep_tables:
            for table in _LEGACY_TABLES:
                conn.execute(f"DROP TABLE IF EXISTS {table}")  # noqa: S608 - fixed list
            print(f"\nDropped: {', '.join(_LEGACY_TABLES)}")
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"\nFAILED, rolled back: {exc}")
        print(f"The database is unchanged. Backup remains at {backup}")
        return 1
    finally:
        conn.close()

    print(f"\nDone: {migrated} quiz(zes) migrated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
