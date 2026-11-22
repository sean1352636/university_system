"""Lesson content attached to a scheduled slot.

The Lesson Planner used to own a second timetable. ``lesson_plans`` carried
its own ``day``/``start``/``end``/``room``/``instructor`` as free text, with no
term, no recurrence, no room or instructor foreign key, and no visibility to
the conflict detector — so a lesson typed into the planner could sit on top of
a module scheduled in Module Scheduling and nothing noticed. Its private
``lesson_courses`` table duplicated the course catalogue, and its save was
``DELETE FROM lesson_plans`` followed by a bulk re-INSERT, so two people with
the planner open silently overwrote each other.

The timetable itself now lives in exactly one place — ``module_schedule``,
which already has ``room_id`` → ``rooms``, ``instructor_id`` → ``instructors``,
semester/year, draft/published status and rollover via ``parent_schedule_id``,
and which Timetable Management and the student timetable already read.

What the planner genuinely owned is what stays here: the *content* of a
session — its title, delivery type and notes — hanging off the slot that says
when and where it happens.

``schedule_id`` is nullable on purpose. A lesson whose module no longer exists
cannot be given a slot (``module_schedule.module_code`` is a foreign key onto
``modules``), and losing the lesson would be worse than keeping it unscheduled,
so those land here with ``schedule_id IS NULL`` and are listed as needing a
slot rather than quietly dropped.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from education_system.systems.university.infrastructure.database.db import (
    sqlite3,
    get_connection,
)

logger = logging.getLogger(__name__)

#: Session types offered for a lesson; mirrors module_schedule.session_type.
LESSON_TYPES = ("Lecture", "Lab", "Tutorial", "Seminar", "Workshop", "Other")

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS lesson_plan_content (
        lesson_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        schedule_id  INTEGER REFERENCES module_schedule(id) ON DELETE CASCADE,
        module_code  TEXT,
        title        TEXT NOT NULL DEFAULT '',
        lesson_type  TEXT NOT NULL DEFAULT '',
        notes        TEXT,
        legacy_slot  TEXT,
        created_at   TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
        updated_by   TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_lesson_content_schedule "
    "ON lesson_plan_content (schedule_id)",
    "CREATE INDEX IF NOT EXISTS idx_lesson_content_module "
    "ON lesson_plan_content (module_code)",
)


def ensure_schema(conn=None) -> bool:
    """Create the lesson-content table. Idempotent."""
    own = conn is None
    try:
        if own:
            conn = get_connection()
        for stmt in _SCHEMA:
            conn.execute(stmt)
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("lesson content schema init failed: %s", exc)
        return False
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------

def scheduled_slots(*, semester: Optional[str] = None, year: Optional[str] = None,
                    module_code: Optional[str] = None, conn=None) -> list[dict]:
    """Slots from ``module_schedule``, with room, instructor and any lesson.

    This is the list the Lesson Plans tab shows: the real timetable, with the
    lesson content (where one has been written) alongside it.
    """
    sql = """
        SELECT ms.id                AS schedule_id,
               ms.module_code       AS module_code,
               COALESCE(m.module_name, ms.module_code) AS module_name,
               ms.day_of_week       AS day_of_week,
               ms.start_time        AS start_time,
               ms.end_time          AS end_time,
               ms.session_type      AS session_type,
               ms.semester          AS semester,
               ms.year              AS year,
               ms.status            AS status,
               COALESCE(NULLIF(TRIM(r.building || ' ' || r.room_number), ''),
                        CAST(ms.room_id AS TEXT), '') AS room,
               TRIM(COALESCE(i.first_name, '') || ' ' || COALESCE(i.last_name, ''))
                                    AS instructor,
               lc.lesson_id         AS lesson_id,
               lc.title             AS title,
               lc.lesson_type       AS lesson_type,
               lc.notes             AS notes
          FROM module_schedule ms
          LEFT JOIN modules m     ON m.module_code = ms.module_code
          LEFT JOIN rooms r       ON r.id = ms.room_id
          LEFT JOIN instructors i ON i.id = ms.instructor_id
          LEFT JOIN lesson_plan_content lc ON lc.schedule_id = ms.id
         WHERE 1 = 1
    """
    params: list[Any] = []
    if semester:
        sql += " AND ms.semester = ?"
        params.append(semester)
    if year:
        sql += " AND CAST(ms.year AS TEXT) = ?"
        params.append(str(year))
    if module_code:
        sql += " AND ms.module_code = ?"
        params.append(module_code)
    sql += (" ORDER BY CASE ms.day_of_week"
            "   WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3"
            "   WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6"
            "   ELSE 7 END, ms.start_time, ms.module_code")
    return _rows(sql, params, conn=conn)


def unscheduled_lessons(*, conn=None) -> list[dict]:
    """Lesson content with no slot — migrated rows that need one."""
    return _rows(
        "SELECT lesson_id, module_code, title, lesson_type, notes, legacy_slot "
        "FROM lesson_plan_content WHERE schedule_id IS NULL "
        "ORDER BY module_code, title",
        [], conn=conn,
    )


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

def save_lesson(schedule_id: Optional[int], *, title: str, lesson_type: str = "",
                notes: str = "", module_code: Optional[str] = None,
                lesson_id: Optional[int] = None, updated_by: Optional[str] = None,
                conn=None) -> Optional[int]:
    """Create or update the lesson content for a slot. Returns its id.

    One lesson per slot: saving again against the same ``schedule_id`` updates
    that lesson rather than adding a second, which is what the old
    delete-everything-and-reinsert save was really trying to achieve.
    """
    own = conn is None
    try:
        if own:
            conn = get_connection()
        ensure_schema(conn)

        if lesson_id is None and schedule_id is not None:
            row = conn.execute(
                "SELECT lesson_id FROM lesson_plan_content WHERE schedule_id = ?",
                (schedule_id,),
            ).fetchone()
            if row:
                lesson_id = row[0]

        if lesson_id is None:
            cur = conn.execute(
                "INSERT INTO lesson_plan_content (schedule_id, module_code, title, "
                "lesson_type, notes, updated_by) VALUES (?,?,?,?,?,?)",
                (schedule_id, module_code, title, lesson_type, notes,
                 str(updated_by) if updated_by else None),
            )
            lesson_id = cur.lastrowid
        else:
            conn.execute(
                "UPDATE lesson_plan_content SET schedule_id = ?, module_code = ?, "
                "title = ?, lesson_type = ?, notes = ?, updated_by = ?, "
                "updated_at = datetime('now') WHERE lesson_id = ?",
                (schedule_id, module_code, title, lesson_type, notes,
                 str(updated_by) if updated_by else None, lesson_id),
            )
        conn.commit()
        return lesson_id
    except Exception as exc:
        logger.warning("save_lesson failed: %s", exc)
        return None
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


def delete_lesson(lesson_id: int, *, conn=None) -> bool:
    """Remove lesson content. The slot itself is untouched.

    Deleting a lesson plan must not delete the teaching slot — that is
    Module Scheduling's to remove, and dropping it here would silently take a
    class off the timetable.
    """
    own = conn is None
    try:
        if own:
            conn = get_connection()
        ensure_schema(conn)
        conn.execute("DELETE FROM lesson_plan_content WHERE lesson_id = ?",
                     (lesson_id,))
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("delete_lesson(%s) failed: %s", lesson_id, exc)
        return False
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


def attach_to_slot(lesson_id: int, schedule_id: int, *, conn=None) -> bool:
    """Give an unscheduled lesson a slot."""
    own = conn is None
    try:
        if own:
            conn = get_connection()
        ensure_schema(conn)
        module = conn.execute(
            "SELECT module_code FROM module_schedule WHERE id = ?", (schedule_id,)
        ).fetchone()
        conn.execute(
            "UPDATE lesson_plan_content SET schedule_id = ?, module_code = ?, "
            "updated_at = datetime('now') WHERE lesson_id = ?",
            (schedule_id, module[0] if module else None, lesson_id),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("attach_to_slot(%s, %s) failed: %s", lesson_id, schedule_id, exc)
        return False
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


# ---------------------------------------------------------------------------
# Migration off the planner's private tables
# ---------------------------------------------------------------------------

def migrate_legacy_lessons(*, apply: bool = False, conn=None) -> dict[str, Any]:
    """Move ``lesson_plans`` rows onto scheduled slots.

    For each legacy lesson we look for a ``module_schedule`` slot with the same
    module, day and start time. Where one exists the lesson attaches to it;
    where the module exists but has no such slot, the slot is created (as a
    draft, so a migrated guess never appears on a published timetable); where
    the module itself is gone, the content is kept unscheduled.

    Report by default; pass ``apply=True`` to write. Idempotent — a legacy row
    already migrated is skipped.
    """
    own = conn is None
    result: dict[str, Any] = {"attached": [], "slot_created": [], "unscheduled": [],
                              "skipped": [], "applied": False}
    try:
        if own:
            conn = get_connection()
        ensure_schema(conn)

        try:
            legacy = conn.execute(
                "SELECT id, course, title, instructor, type, day, start, end, "
                "room, notes FROM lesson_plans ORDER BY id"
            ).fetchall()
        except sqlite3.OperationalError:
            return result           # planner tables already gone

        known_modules = {r[0] for r in conn.execute(
            "SELECT module_code FROM modules WHERE COALESCE(TRIM(module_code),'') <> ''")}

        for row in legacy:
            lesson = dict(row) if hasattr(row, "keys") else dict(zip(
                ("id", "course", "title", "instructor", "type", "day", "start",
                 "end", "room", "notes"), row))
            # The planner stored course as "CODE - Course Name".
            code = str(lesson.get("course") or "").split("-")[0].strip()
            slot_text = (f"{lesson.get('day') or ''} "
                         f"{lesson.get('start') or ''}-{lesson.get('end') or ''} "
                         f"{lesson.get('room') or ''}").strip()

            already = conn.execute(
                "SELECT 1 FROM lesson_plan_content WHERE title = ? AND "
                "COALESCE(module_code,'') = ? AND COALESCE(legacy_slot,'') = ?",
                (lesson.get("title") or "", code, slot_text),
            ).fetchone()
            if already:
                result["skipped"].append(code)
                continue

            match = conn.execute(
                "SELECT id FROM module_schedule WHERE module_code = ? "
                "AND day_of_week = ? AND start_time = ?",
                (code, lesson.get("day"), lesson.get("start")),
            ).fetchone()

            entry = {"legacy_id": lesson["id"], "module_code": code,
                     "title": lesson.get("title"), "slot": slot_text}

            if match:
                entry["schedule_id"] = match[0]
                result["attached"].append(entry)
                if apply:
                    _insert_content(conn, match[0], code, lesson, slot_text)
            elif code in known_modules:
                result["slot_created"].append(entry)
                if apply:
                    cur = conn.execute(
                        "INSERT INTO module_schedule (module_code, day_of_week, "
                        "start_time, end_time, session_type, status, recurrence) "
                        "VALUES (?,?,?,?,?, 'draft', 'weekly')",
                        (code, lesson.get("day"), lesson.get("start"),
                         lesson.get("end"), lesson.get("type") or "Lecture"),
                    )
                    _insert_content(conn, cur.lastrowid, code, lesson, slot_text)
            else:
                # Module gone (deleted placeholder, renamed catalogue): keep
                # the content rather than lose it.
                entry["reason"] = "module not in catalogue"
                result["unscheduled"].append(entry)
                if apply:
                    _insert_content(conn, None, code, lesson, slot_text)

        if apply:
            conn.commit()
            result["applied"] = True
    except Exception as exc:
        logger.warning("migrate_legacy_lessons failed: %s", exc)
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
    return result


def _insert_content(conn, schedule_id, code, lesson, slot_text) -> None:
    conn.execute(
        "INSERT INTO lesson_plan_content (schedule_id, module_code, title, "
        "lesson_type, notes, legacy_slot, updated_by) VALUES (?,?,?,?,?,?,?)",
        (schedule_id, code, lesson.get("title") or "", lesson.get("type") or "",
         lesson.get("notes"), slot_text, "migration"),
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _rows(sql: str, params: list, *, conn=None) -> list[dict]:
    own = conn is None
    try:
        if own:
            conn = get_connection()
        ensure_schema(conn)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) if hasattr(r, "keys") else r for r in rows]
    except Exception as exc:
        logger.warning("lesson plan query failed: %s", exc)
        return []
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
