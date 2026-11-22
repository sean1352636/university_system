"""What the course-section form offers, and how a section is removed.

* **Instructors** are the active ones (not on leave, not left). The section
  stores the name, because ``course_sections.instructor`` is text that the
  calendar and the timetable show as written.
* **Locations** are the available rooms, then any teaching building with no
  rooms on file. Residences are left out: nothing is taught in a dormitory.
* **Enrolled** is who is actually placed on the section; while nobody is (the
  normal case, enrolment is mostly module-level) it is the students on the
  course, counted the way the rest of the system counts them.
* **Deleting** takes the section's meeting times with it, because they mean
  nothing without it. Anything that refers to the section from elsewhere —
  students, a waitlist, timetable slots, teaching assistants — stops the delete,
  since those references carry no foreign key and would otherwise dangle.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import logging

from education_system.systems.university.application.programmes import course_team

logger = logging.getLogger(__name__)

_NON_TEACHING_BUILDINGS = ("residence", "residential", "dormitory", "housing")


def _columns(conn, table) -> set[str]:
    # db-audit: ignore[DBW001] - table names here are literals from this module
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def instructor_names(conn) -> list[str]:
    """Names of the instructors who can be given a section, A to Z."""
    cols = _columns(conn, "instructors")
    where = "WHERE COALESCE(is_active, 1) = 1"
    if "status" in cols:
        where += " AND LOWER(COALESCE(NULLIF(status, ''), 'active')) = 'active'"
    # db-audit: ignore[DBW001] - literal clauses only
    rows = conn.execute("SELECT COALESCE(first_name, ''), COALESCE(last_name, '') "
                        f"FROM instructors {where} "
                        "ORDER BY last_name COLLATE NOCASE, first_name COLLATE NOCASE").fetchall()
    names = [" ".join(p.strip() for p in tuple(r) if p and p.strip()) for r in rows]
    return list(dict.fromkeys(n for n in names if n))


def locations(conn) -> dict[str, int | None]:
    """``{label: capacity}`` for everywhere a section can meet.

    Capacity is None when none is recorded. A room saved with 0 counts as
    none: no room seats nobody, it just has not been filled in.
    """
    out: dict[str, int | None] = {}
    if _columns(conn, "rooms"):
        where = "WHERE COALESCE(is_active, 1) = 1"
        if "status" in _columns(conn, "rooms"):
            where += " AND LOWER(COALESCE(NULLIF(status, ''), 'available')) = 'available'"
        # db-audit: ignore[DBW001] - literal clauses only
        for rid, number, building, capacity in conn.execute(
                f"SELECT id, room_number, building, capacity FROM rooms {where} "
                "ORDER BY building COLLATE NOCASE, room_number COLLATE NOCASE").fetchall():
            label = " — ".join(filter(None, [number or f"Room {rid}", building]))
            out[label] = int(capacity) if capacity else None
    if _columns(conn, "buildings"):
        taken = conn.execute(
            "SELECT DISTINCT LOWER(COALESCE(building, '')) FROM rooms "
            "WHERE COALESCE(is_active, 1) = 1").fetchall() if _columns(conn, "rooms") else []
        with_rooms = {r[0] for r in taken}
        for name, kind in conn.execute(
                "SELECT building_name, COALESCE(building_type, '') FROM buildings "
                "WHERE COALESCE(is_active, 1) = 1 "
                "ORDER BY building_name COLLATE NOCASE").fetchall():
            if (name and name.lower() not in with_rooms
                    and kind.lower() not in _NON_TEACHING_BUILDINGS):
                out[name] = None
    return out


def enrolled_count(conn, course_code, section_id=None) -> int:
    """How many students a section has, or would have, on *course_code*."""
    if section_id is not None and "section_id" in _columns(conn, "student_modules"):
        placed = conn.execute("SELECT COUNT(*) FROM student_modules "
                              "WHERE section_id = ? AND status = 'Enrolled'",
                              (section_id,)).fetchone()[0]
        if placed:
            return int(placed)
    try:
        return len(course_team.students_on(conn, course_code))
    except ValueError:      # a code that is not a course, such as a module delivery
        return 0


#: (table, condition, wording) for what refers to a section without a foreign key.
_REFERENCES = {
    "students": ("student_modules", "", "student enrolment(s)"),
    "waitlist": ("module_waitlist", " AND status = 'waiting'", "student(s) on the waitlist"),
    "timetable": ("module_schedule", " AND LOWER(COALESCE(status, '')) <> 'cancelled'",
                  "timetable slot(s)"),
    "assistants": ("ta_assignments", "", "teaching assistant assignment(s)"),
}


def delete_blockers(conn, section_id) -> dict[str, int]:
    """What still refers to the section, as ``{kind: count}``. Empty means free."""
    found = {}
    for kind, (table, condition, _wording) in _REFERENCES.items():
        if "section_id" not in _columns(conn, table):
            continue
        # db-audit: ignore[DBW001] - table and condition are literals from _REFERENCES
        count = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE section_id = ?{condition}",
                             (section_id,)).fetchone()[0]
        if count:
            found[kind] = int(count)
    return found


def describe_blockers(blockers) -> str:
    return "\n".join(f"  • {count} {_REFERENCES[kind][2]}" for kind, count in blockers.items())


def meeting_ids(conn, section_id) -> list[int]:
    return [int(r[0]) for r in conn.execute(
        "SELECT id FROM section_meetings WHERE section_id = ? ORDER BY id", (section_id,))]


def delete_section(conn, section_id) -> list[int]:
    """Delete the section and its meetings; returns the meeting ids removed.

    Pass those to :func:`clear_calendar` once the delete is committed. Raises
    ValueError if anything still refers to the section.
    """
    blockers = delete_blockers(conn, section_id)
    if blockers:
        raise ValueError("This section is still in use:\n" + describe_blockers(blockers))
    removed = meeting_ids(conn, section_id)
    conn.execute("DELETE FROM section_meetings WHERE section_id = ?", (section_id,))
    conn.execute("DELETE FROM course_sections WHERE id = ?", (section_id,))
    return removed


def cancel_section(conn, section_id):
    conn.execute("UPDATE course_sections SET status = 'Cancelled', "
                 "updated_at = datetime('now') WHERE id = ?", (section_id,))


def clear_calendar(ids) -> int:
    """Remove removed meetings from the academic calendar.

    Runs after the delete has committed: the calendar is a mirror, so a failure
    here is logged rather than bringing the section back.
    """
    from education_system.systems.university.domains.teaching.domain.section_meeting_calendar import (
        unsync_meeting,
    )
    cleared = 0
    for meeting_id in ids:
        try:
            cleared += unsync_meeting(meeting_id)
        except Exception:
            logger.exception("calendar clear failed for meeting %s", meeting_id)
    return cleared
