"""Bridge between the university's two parallel scheduling models.

The system grew two independent timetabling data models:

* **Module-based** — ``modules`` / ``module_schedule`` (room_id → ``rooms``) /
  ``student_modules``. Drives the Module Scheduling GUI and the student
  "My Timetable".
* **Section-based** — ``courses`` / ``course_sections`` / ``section_meetings``
  (free-text ``location``), inside ``academic_terms``. Drives the Course
  Management → Timetable tab.

They never talked to each other: a student couldn't see section meetings, and
neither scheduler knew about the other's room usage. This module reconciles
them with three capabilities:

1. ``course_module_map`` — an explicit course_code ↔ module_code mapping, plus
   automatic identity linking where the two codes are the same string.
2. ``get_student_section_meetings`` — section meetings for the courses a student
   is (transitively) enrolled in, shaped for the student timetable grid.
3. ``find_timetable_conflicts`` — overlap detection that checks BOTH
   ``section_meetings`` (by location) and ``module_schedule`` (by room), so
   either scheduler can warn about clashes created in the other.

Everything is best-effort: any missing table or bad row is skipped rather than
raising, so a partially-provisioned database never breaks a caller.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from education_system.post_18.university_system.infrastructure.database.db import get_connection

# Term statuses that should NOT surface in a live student timetable.
_INACTIVE_TERM_STATUSES = ("Archived", "Completed", "Closed", "Cancelled")


def _to_minutes(hhmm: Optional[str]) -> Optional[int]:
    """Parse 'HH:MM' (or 'HH:MM:SS') into minutes-since-midnight, or None."""
    if not hhmm:
        return None
    try:
        parts = str(hhmm).strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return None


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """True if [a_start,a_end) and [b_start,b_end) intersect."""
    return a_start < b_end and a_end > b_start


# ---------------------------------------------------------------------------
# Schema + mapping (reconciliation)
# ---------------------------------------------------------------------------
def ensure_bridge_schema(conn) -> None:
    """Create the course↔module mapping table if it doesn't exist."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS course_module_map (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               course_code TEXT NOT NULL,
               module_code TEXT NOT NULL,
               link_source TEXT NOT NULL DEFAULT 'manual',
               created_at  TEXT NOT NULL DEFAULT (datetime('now')),
               UNIQUE(course_code, module_code)
           )""")
    conn.commit()


def auto_link_matching_codes(conn) -> int:
    """Seed identity links where a course_code also exists as a module_code.

    Returns the number of rows inserted this call (0 if all already present)."""
    try:
        cur = conn.execute(
            """INSERT OR IGNORE INTO course_module_map (course_code, module_code, link_source)
               SELECT c.course_code, m.module_code, 'auto'
                 FROM courses c JOIN modules m ON c.course_code = m.module_code""")
        conn.commit()
        return cur.rowcount or 0
    except Exception:
        return 0


def link_course_module(course_code: str, module_code: str, conn=None) -> bool:
    """Manually link a course to a module. Idempotent."""
    close = conn is None
    conn = conn or get_connection()
    try:
        ensure_bridge_schema(conn)
        conn.execute(
            "INSERT OR IGNORE INTO course_module_map (course_code, module_code, link_source) "
            "VALUES (?, ?, 'manual')", (course_code, module_code))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        if close:
            conn.close()


def unlink_course_module(course_code: str, module_code: str, conn=None) -> bool:
    close = conn is None
    conn = conn or get_connection()
    try:
        conn.execute(
            "DELETE FROM course_module_map WHERE course_code=? AND module_code=?",
            (course_code, module_code))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        if close:
            conn.close()


def list_links(conn=None) -> List[Dict[str, str]]:
    """Return all course↔module links (explicit + auto-seeded)."""
    close = conn is None
    conn = conn or get_connection()
    try:
        ensure_bridge_schema(conn)
        auto_link_matching_codes(conn)
        rows = conn.execute(
            "SELECT course_code, module_code, link_source FROM course_module_map "
            "ORDER BY course_code, module_code").fetchall()
        return [{"course_code": r[0], "module_code": r[1], "link_source": r[2]}
                for r in rows]
    except Exception:
        return []
    finally:
        if close:
            conn.close()


def linked_course_codes_for_modules(conn, module_codes) -> Set[str]:
    """Course codes linked to any of *module_codes* — via the explicit map AND
    identity (a course whose code equals one of the module codes)."""
    codes: Set[str] = set()
    module_codes = [m for m in module_codes if m]
    if not module_codes:
        return codes
    placeholders = ",".join("?" * len(module_codes))
    try:
        for r in conn.execute(
                f"SELECT DISTINCT course_code FROM course_module_map "
                f"WHERE module_code IN ({placeholders})", list(module_codes)).fetchall():
            codes.add(r[0])
    except Exception:
        pass
    try:
        for r in conn.execute(
                f"SELECT DISTINCT course_code FROM courses "
                f"WHERE course_code IN ({placeholders})", list(module_codes)).fetchall():
            codes.add(r[0])
    except Exception:
        pass
    return codes


# ---------------------------------------------------------------------------
# Student read-through (section meetings → student timetable)
# ---------------------------------------------------------------------------
def get_student_section_meetings(student_id: str, conn=None) -> List[Dict[str, str]]:
    """Section meetings for the courses *student_id* is (transitively) enrolled
    in, for terms that are still active.

    Each dict has: day_of_week, start_time, end_time, code, name, session_type,
    location — matching what the student "My Timetable" grid consumes."""
    close = conn is None
    conn = conn or get_connection()
    out: List[Dict[str, str]] = []
    try:
        ensure_bridge_schema(conn)
        auto_link_matching_codes(conn)

        mods = [r[0] for r in conn.execute(
            "SELECT module_code FROM student_modules WHERE student_id=?",
            (student_id,)).fetchall()]
        course_codes = linked_course_codes_for_modules(conn, mods)
        if not course_codes:
            return out

        placeholders = ",".join("?" * len(course_codes))
        status_ph = ",".join("?" * len(_INACTIVE_TERM_STATUSES))
        rows = conn.execute(
            f"""SELECT sm.day_of_week, sm.start_time, sm.end_time,
                       cs.course_code, COALESCE(c.course_name, cs.course_code),
                       cs.section_number,
                       COALESCE(NULLIF(TRIM(sm.location), ''), rm.room_number, 'TBA')
                  FROM section_meetings sm
                  JOIN course_sections cs ON cs.id = sm.section_id
                  LEFT JOIN courses c        ON c.course_code = cs.course_code
                  LEFT JOIN academic_terms t ON t.id = cs.term_id
                  LEFT JOIN rooms rm         ON rm.id = sm.room_id
                 WHERE cs.course_code IN ({placeholders})
                   AND (t.status IS NULL OR t.status NOT IN ({status_ph}))""",
            list(course_codes) + list(_INACTIVE_TERM_STATUSES)).fetchall()

        seen = set()
        for r in rows:
            key = (r[0], r[1], r[2], r[3], r[6])
            if key in seen:
                continue
            seen.add(key)
            label = r[4]
            label = f"{label} ({r[3]}-{r[5]})" if r[5] else f"{label} ({r[3]})"
            out.append({
                "day_of_week": r[0], "start_time": r[1], "end_time": r[2],
                "code": r[3], "name": label, "session_type": "Class",
                "location": r[6] or "TBA",
            })
    except Exception:
        pass
    finally:
        if close:
            conn.close()
    return out


# ---------------------------------------------------------------------------
# Cross-system room/time conflict detection
# ---------------------------------------------------------------------------
def find_timetable_conflicts(day_of_week: str, start_time: str, end_time: str,
                             location: Optional[str] = None,
                             room_id: Optional[int] = None,
                             exclude_section_meeting_id: Optional[int] = None,
                             conn=None) -> List[str]:
    """Return human-readable descriptions of meetings that clash with the given
    slot in the same room, across BOTH scheduling models.

    A clash needs the same day, an overlapping time range, and a matching room.
    Matching is precise when *room_id* is given (both models share ``rooms``);
    otherwise it falls back to *location* text — section meetings by exact
    location, module schedule by the location containing the room's number.
    Passing neither *room_id* nor *location* returns ``[]``."""
    start_m = _to_minutes(start_time)
    end_m = _to_minutes(end_time)
    loc = (location or "").strip()
    if start_m is None or end_m is None or (not loc and not room_id):
        return []

    close = conn is None
    conn = conn or get_connection()
    conflicts: List[str] = []
    try:
        # 1) Section meetings — by room_id (precise) and/or location text.
        sec_rows: Dict[int, tuple] = {}
        sec_sql = ("SELECT sm.id, sm.start_time, sm.end_time, "
                   "COALESCE(NULLIF(TRIM(sm.location),''), rm.room_number, 'a room'), "
                   "cs.course_code, cs.section_number "
                   "FROM section_meetings sm "
                   "JOIN course_sections cs ON cs.id = sm.section_id "
                   "LEFT JOIN rooms rm ON rm.id = sm.room_id "
                   "WHERE sm.day_of_week = ? AND ")
        try:
            if room_id:
                for r in conn.execute(sec_sql + "sm.room_id = ?",
                                      (day_of_week, room_id)).fetchall():
                    sec_rows[r[0]] = r
            if loc:
                for r in conn.execute(
                        sec_sql + "TRIM(LOWER(sm.location)) = TRIM(LOWER(?))",
                        (day_of_week, loc)).fetchall():
                    sec_rows[r[0]] = r
        except Exception:
            pass
        for sid, r in sec_rows.items():
            if exclude_section_meeting_id and sid == exclude_section_meeting_id:
                continue
            bs, be = _to_minutes(r[1]), _to_minutes(r[2])
            if bs is None or be is None or not _overlaps(start_m, end_m, bs, be):
                continue
            where = r[3] or "room"
            conflicts.append(
                f"Section {r[4]}-{r[5]} already uses {where} ({r[1]}–{r[2]})")

        # 2) Module-schedule classes — by room_id (precise) and/or room number.
        mod_rows: Dict[int, tuple] = {}
        mod_sql = ("SELECT ms.id, ms.start_time, ms.end_time, ms.module_code, "
                   "COALESCE(r.room_number,''), COALESCE(r.building,'') "
                   "FROM module_schedule ms LEFT JOIN rooms r ON r.id = ms.room_id "
                   "WHERE ms.day_of_week = ? AND ")
        try:
            if room_id:
                for r in conn.execute(mod_sql + "ms.room_id = ?",
                                      (day_of_week, room_id)).fetchall():
                    mod_rows[r[0]] = r
            if loc:
                for r in conn.execute(
                        mod_sql + "r.room_number IS NOT NULL AND TRIM(r.room_number) <> '' "
                        "AND LOWER(?) LIKE '%' || LOWER(r.room_number) || '%'",
                        (day_of_week, loc)).fetchall():
                    mod_rows[r[0]] = r
        except Exception:
            pass
        for r in mod_rows.values():
            bs, be = _to_minutes(r[1]), _to_minutes(r[2])
            if bs is None or be is None or not _overlaps(start_m, end_m, bs, be):
                continue
            room = r[4] if not r[5] else f"{r[5]} {r[4]}"
            conflicts.append(
                f"Module {r[3]} already uses room {room} ({r[1]}–{r[2]})")
    finally:
        if close:
            conn.close()
    return conflicts
