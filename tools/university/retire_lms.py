#!/usr/bin/env python3
"""Retire the internal LMS: migrate what's worth keeping, drop the rest.

The LMS was a third naming layer over concepts the university already models.
``lms_courses`` keyed on a ``module_code`` and carried an instructor, dates,
an enrolment cap and a published flag — every one of which ``modules`` already
holds for 380 modules, with 198 real enrolments in ``student_modules``. The
content layer that would have justified it (``lms_modules`` -> ``lms_lessons``
-> ``lms_progress``, i.e. sequenced lessons with per-student completion) was
never populated.

Its other features were merged into their natural homes first: quizzes into
``assignments`` + the exam portal, the gradebook into Grade Tracking,
discussion forums into chat rooms.

What this does
--------------
* ``lms_course_content`` (+ any ``lms_video_lectures`` attached) -> rows in
  ``course_materials``, which already keys teaching material by course_code.
* Everything else is reported, then the LMS tables are dropped.

Not touched: ``lms_access_grants`` belongs to absence tracking (#46), not to
this feature, and the Canvas/Moodle integration under
``platform/delivery/api/lms_routes.py`` is a different thing entirely.

Nothing runs without ``--apply``; a dry run is the default. ``--apply`` copies
the database into ``var/backups/maintenance/lms_retirement/<timestamp>/``
first.

    python -m tools.university.retire_lms            # dry run
    python -m tools.university.retire_lms --apply
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

#: Dropped in this order so a child table never outlives its parent.
LMS_TABLES = (
    "lms_quiz_submissions", "lms_quiz_attempts", "lms_quiz_questions",
    "lms_quizzes", "lms_questions",
    "lms_discussion_posts", "lms_discussion_forums",
    "lms_video_lectures", "lms_course_content",
    "lms_student_enrollment", "lms_gradebook",
    "lms_progress", "lms_lessons", "lms_modules", "lms_resources",
    "lms_courses",
)

#: Named so nobody removes them by pattern-matching on the prefix.
KEEP_TABLES = {
    "lms_access_grants": "absence tracking (#46), unrelated to this feature",
}


def _table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def survey(conn):
    """Row counts for every LMS table present."""
    counts = {}
    for table in LMS_TABLES:
        if _table_exists(conn, table):
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
    return counts


def plan_content(conn):
    """The ``lms_course_content`` rows and where each would land."""
    if not _table_exists(conn, "lms_course_content"):
        return []
    rows = conn.execute(
        """SELECT c.content_id, c.content_type, c.title, c.description,
                  c.content_url, c.release_date, co.module_code,
                  v.video_url, v.duration_minutes
             FROM lms_course_content c
             LEFT JOIN lms_courses co ON co.lms_course_id = c.lms_course_id
             LEFT JOIN lms_video_lectures v ON v.content_id = c.content_id
            ORDER BY c.content_id"""
    ).fetchall()

    plan = []
    for (cid, ctype, title, desc, url, released, module_code,
         video_url, duration) in rows:
        course_code = module_code
        resolvable = bool(course_code) and conn.execute(
            "SELECT 1 FROM courses WHERE COALESCE(course_code, code) = ? LIMIT 1",
            (course_code,)).fetchone() is not None
        plan.append({
            "content_id": cid, "title": title or "(untitled)",
            "material_type": ctype or "Resource",
            "course_code": course_code,
            "url": video_url or url or "",
            "notes": " ".join(x for x in (
                desc or "",
                f"Released {released}." if released else "",
                f"Video {video_url} ({duration} min)." if video_url else "",
            ) if x).strip(),
            "blocker": None if resolvable else (
                f"course_code {course_code!r} is not in courses"),
        })
    return plan


FORUM_TABLES_SQL = (
    """CREATE TABLE IF NOT EXISTS module_forums (
        forum_id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_code TEXT NOT NULL,
        topic TEXT NOT NULL,
        description TEXT,
        created_by TEXT NOT NULL,
        is_pinned INTEGER DEFAULT 0,
        is_locked INTEGER DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (module_code) REFERENCES modules(module_code)
    )""",
    """CREATE TABLE IF NOT EXISTS module_forum_posts (
        post_id INTEGER PRIMARY KEY AUTOINCREMENT,
        forum_id INTEGER,
        user_id TEXT,
        content TEXT,
        parent_post_id INTEGER,
        attachments TEXT,
        likes_count INTEGER DEFAULT 0,
        is_instructor_post INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (forum_id) REFERENCES module_forums(forum_id) ON DELETE CASCADE
    )""",
)


def plan_forums(conn):
    """Module Discussion Forums rows to rehome, with their module code.

    That feature (#39) stored in ``lms_discussion_forums``/``_posts`` because
    their foreign key pointed at ``lms_courses``; it is keyed on the module
    now, so its data moves rather than being dropped with the LMS.
    """
    if not _table_exists(conn, "lms_discussion_forums"):
        return []
    rows = conn.execute(
        """SELECT f.forum_id, f.topic, f.description, f.created_by,
                  f.is_pinned, f.is_locked, f.created_at, co.module_code,
                  (SELECT COUNT(*) FROM lms_discussion_posts p
                    WHERE p.forum_id = f.forum_id)
             FROM lms_discussion_forums f
             LEFT JOIN lms_courses co ON co.lms_course_id = f.lms_course_id
            ORDER BY f.forum_id"""
    ).fetchall()
    return [{
        "forum_id": r[0], "topic": r[1], "description": r[2], "created_by": r[3],
        "is_pinned": r[4], "is_locked": r[5], "created_at": r[6],
        "module_code": r[7], "posts": r[8],
        "blocker": None if r[7] else "its LMS course has no module_code",
    } for r in rows]


def migrate_forums(conn, plan):
    """Copy forums and their posts into the module-keyed tables."""
    for sql in FORUM_TABLES_SQL:
        conn.execute(sql)
    moved_forums = moved_posts = 0
    for entry in plan:
        if entry["blocker"]:
            continue
        cur = conn.execute(
            """INSERT INTO module_forums
                   (module_code, topic, description, created_by, is_pinned,
                    is_locked, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (entry["module_code"], entry["topic"], entry["description"],
             entry["created_by"], entry["is_pinned"], entry["is_locked"],
             entry["created_at"]))
        new_id = cur.lastrowid
        for post in conn.execute(
            """SELECT user_id, content, parent_post_id, attachments,
                      likes_count, is_instructor_post, created_at
                 FROM lms_discussion_posts WHERE forum_id = ?
                ORDER BY post_id""", (entry["forum_id"],)).fetchall():
            conn.execute(
                """INSERT INTO module_forum_posts
                       (forum_id, user_id, content, parent_post_id, attachments,
                        likes_count, is_instructor_post, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (new_id, *post))
            moved_posts += 1
        moved_forums += 1
    return moved_forums, moved_posts


def migrate_content(conn, plan):
    """Write the migratable content rows into ``course_materials``."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    written = 0
    for entry in plan:
        if entry["blocker"]:
            continue
        conn.execute(
            """INSERT INTO course_materials
                   (course_code, material_type, title, url, notes,
                    required, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 0, ?, ?)""",
            (entry["course_code"], entry["material_type"], entry["title"],
             entry["url"], entry["notes"], now, now),
        )
        written += 1
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true",
                        help="actually write; without it this is a dry run")
    parser.add_argument("--db", help="database to operate on (default: the live one)")
    parser.add_argument("--keep-tables", action="store_true",
                        help="migrate the content but leave the tables in place")
    args = parser.parse_args(argv)

    from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH, maintenance_backup_dir
    db_path = Path(args.db) if args.db else Path(UNIVERSITY_DEFAULT_DB_PATH)
    if not db_path.exists():
        print(f"No such database: {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    counts = survey(conn)
    plan = plan_content(conn)
    forums = plan_forums(conn)

    print(f"Database: {db_path}\n")
    print("LMS tables present:")
    total = 0
    for table, n in counts.items():
        total += n
        print(f"  {table:<26} {n:>4} row(s)")
    print(f"  {'':<26} {total:>4} rows in total\n")

    for table, why in KEEP_TABLES.items():
        if _table_exists(conn, table):
            print(f"Keeping {table} — {why}")
    print()

    print("Teaching material to migrate into course_materials:")
    if not plan:
        print("  (none)")
    for entry in plan:
        state = f"BLOCKED — {entry['blocker']}" if entry["blocker"] else \
            f"-> course_materials({entry['course_code']}, {entry['material_type']})"
        print(f"  {entry['title']!r}  {state}")

    print("\nModule Discussion Forums to rehome (module_forums):")
    if not forums:
        print("  (none)")
    for entry in forums:
        state = f"BLOCKED — {entry['blocker']}" if entry["blocker"] else \
            f"-> module_forums({entry['module_code']}), {entry['posts']} post(s)"
        print(f"  {entry['topic']!r}  {state}")

    dropped_rows = total - sum(1 for e in plan if not e["blocker"])
    print(f"\n{sum(1 for e in plan if not e['blocker'])} row(s) migrated, "
          f"~{dropped_rows} row(s) discarded with the tables.")

    if not args.apply:
        print("\nDry run — nothing written. Re-run with --apply to make these changes.")
        return 0

    backup_dir = maintenance_backup_dir("lms_retirement", create=True)
    backup = backup_dir / db_path.name
    shutil.copy(db_path, backup)
    print(f"\nBackup written to {backup}")

    try:
        written = migrate_content(conn, plan)
        print(f"Migrated {written} material(s) into course_materials.")
        f_moved, p_moved = migrate_forums(conn, forums)
        print(f"Rehomed {f_moved} forum(s) and {p_moved} post(s) into module_forums.")

        if not args.keep_tables:
            dropped = []
            for table in LMS_TABLES:
                if _table_exists(conn, table):
                    conn.execute(f"DROP TABLE IF EXISTS {table}")  # noqa: S608 - fixed list
                    dropped.append(table)
            print(f"Dropped {len(dropped)} table(s): {', '.join(dropped)}")
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"\nFAILED, rolled back: {exc}")
        print(f"The database is unchanged. Backup remains at {backup}")
        return 1
    finally:
        conn.close()

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
