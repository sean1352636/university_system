"""How a module is delivered: teaching team, external examiners, deliveries
(terms / sections), weekly timetable slots, student evaluation results, and
filling in missing credits and levels.

* **Teaching team** (``module_staff``) — one leader per module per academic
  year, plus lecturers, tutors, markers and moderators with their hours. The
  leader is mirrored into ``modules.instructor`` / ``instructor_id`` because
  every older screen reads the instructor from there.
* **Deliveries** are ``course_sections`` rows (``course_code`` holds the
  module code). Once a module has an open delivery the enrolment gate makes a
  student choose one and enforces its capacity and timetable fit.
* **Timetable slots** are ``module_schedule`` rows. Adding one checks the
  room and the instructor against every other published slot on that day.
  Removing one marks it cancelled — attendance registers and generated
  sessions refer to it.
* **Credits / levels**: the seeded modules carry ``credits = 0`` and no
  level. Credits are derived as the programme's requirement divided by its
  module count (the rule Academic Progress and the degree audit already use),
  levels from the year of study (year 1 → FHEQ 4). Every fill goes through
  the change history.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import re
from datetime import date

from education_system.systems.university.application.modules import specification as spec
from education_system.systems.university.application.teaching import occurrences
from education_system.systems.university.infrastructure.database.schemas import (
    module_catalogue_schema as schema,
)

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
SESSION_TYPES = ("Lecture", "Seminar", "Tutorial", "Lab", "Workshop", "Practical")
DELIVERY_MODES = ("In Person", "Online", "Blended")
DELIVERY_STATUSES = ("Open", "Closed", "Cancelled")
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def ensure(conn):
    schema.apply_to_connection(conn)


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _require_module(conn, code):
    if not conn.execute("SELECT 1 FROM modules WHERE module_code = ?", (code,)).fetchone():
        raise ValueError(f"Module {code} does not exist")


# ── teaching team ───────────────────────────────────────────────────────


def staff_choices(conn) -> list[dict]:
    return _dicts(conn.execute(
        "SELECT username, TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) "
        "AS name, role FROM users WHERE COALESCE(role, '') <> 'student' "
        "AND TRIM(COALESCE(username, '')) <> '' ORDER BY username"))


def team(conn, code) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute(
        "SELECT ms.id, ms.username, TRIM(COALESCE(u.first_name, '') || ' ' || "
        "COALESCE(u.last_name, '')) AS name, ms.role, ms.hours, ms.academic_year "
        "FROM module_staff ms LEFT JOIN users u ON u.username = ms.username "
        "WHERE ms.module_code = ? ORDER BY ms.academic_year DESC, "
        "CASE ms.role WHEN 'leader' THEN 0 ELSE 1 END, ms.role, ms.username", (code,)))


def _sync_leader(conn, code):
    """Mirror the current leader into ``modules.instructor``."""
    row = conn.execute("SELECT username FROM module_staff WHERE module_code = ? AND role = 'leader' "
                       "ORDER BY academic_year DESC LIMIT 1", (code,)).fetchone()
    username = row[0] if row else None
    user = conn.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE",
                        (username,)).fetchone() if username else None
    conn.execute("UPDATE modules SET instructor = ?, instructor_id = ? WHERE module_code = ?",
                 (username, user[0] if user else None, code))


def add_member(conn, code, username, role, hours=0, academic_year="", actor=None) -> int:
    ensure(conn)
    _require_module(conn, code)
    username, role = (username or "").strip(), (role or "").strip().lower()
    if role not in schema.STAFF_ROLES:
        raise ValueError(f"Role must be one of: {', '.join(schema.STAFF_ROLES)}")
    if not conn.execute("SELECT 1 FROM users WHERE username = ? COLLATE NOCASE "
                        "AND COALESCE(role, '') <> 'student'", (username,)).fetchone():
        raise ValueError(f"No staff account named {username}")
    hours = spec._number("hours", hours) or 0
    year = (academic_year or "").strip()
    if role == "leader":
        current = conn.execute("SELECT username FROM module_staff WHERE module_code = ? "
                               "AND role = 'leader' AND academic_year = ?", (code, year)).fetchone()
        if current:
            raise ValueError(f"{current[0]} already leads {code}"
                             + (f" in {year}" if year else "") + "; remove them first")
    try:
        cur = conn.execute("INSERT INTO module_staff (module_code, username, role, hours, "
                           "academic_year) VALUES (?, ?, ?, ?, ?)",
                           (code, username, role, hours, year))
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise ValueError(f"{username} is already {role} on {code}") from None
        raise
    if role == "leader":
        _sync_leader(conn, code)
    spec._record(conn, code, {f"team: {role}": (None, f"{username} ({hours:g} h)")}, actor)
    return int(cur.lastrowid)


def remove_member(conn, code, member_id, actor=None) -> bool:
    row = conn.execute("SELECT username, role FROM module_staff WHERE id = ? AND module_code = ?",
                       (member_id, code)).fetchone()
    if row is None:
        return False
    conn.execute("DELETE FROM module_staff WHERE id = ?", (member_id,))
    if row[1] == "leader":
        _sync_leader(conn, code)
    spec._record(conn, code, {f"team: {row[1]}": (row[0], None)}, actor)
    return True


def leader(conn, code):
    ensure(conn)
    row = conn.execute("SELECT username FROM module_staff WHERE module_code = ? AND role = 'leader' "
                       "ORDER BY academic_year DESC LIMIT 1", (code,)).fetchone()
    if row:
        return row[0]
    row = conn.execute("SELECT instructor FROM modules WHERE module_code = ?", (code,)).fetchone()
    return row[0] if row and row[0] else None


def is_leader(conn, code, username) -> bool:
    return bool(username) and (leader(conn, code) or "").lower() == username.lower()


def workload(conn, username) -> dict:
    """Hours per module for one member of staff, and the total."""
    ensure(conn)
    rows = _dicts(conn.execute(
        "SELECT ms.module_code, COALESCE(m.module_name, '') AS module_name, ms.role, ms.hours, "
        "ms.academic_year FROM module_staff ms LEFT JOIN modules m "
        "ON m.module_code = ms.module_code WHERE ms.username = ? COLLATE NOCASE "
        "ORDER BY ms.academic_year DESC, ms.module_code", (username,)))
    return {"rows": rows, "total_hours": sum(r["hours"] or 0 for r in rows)}


# ── external examiners ──────────────────────────────────────────────────


def examiner_choices(conn) -> list[dict]:
    """Active examiners whose appointment has not ended."""
    today = date.today().isoformat()
    return _dicts(conn.execute(
        "SELECT examiner_id, name, institution, appointment_end FROM external_examiners "
        "WHERE LOWER(COALESCE(status, 'active')) = 'active' "
        "AND (appointment_end IS NULL OR appointment_end = '' OR appointment_end >= ?) "
        "ORDER BY name", (today,)))


def module_examiners(conn, code) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute(
        "SELECT me.id, me.examiner_id, e.name, e.institution, e.appointment_end, "
        "me.academic_year FROM module_external_examiners me "
        "JOIN external_examiners e ON e.examiner_id = me.examiner_id "
        "WHERE me.module_code = ? ORDER BY me.academic_year DESC, e.name", (code,)))


def assign_examiner(conn, code, examiner_id, academic_year="", actor=None) -> int:
    ensure(conn)
    _require_module(conn, code)
    examiner = next((e for e in examiner_choices(conn)
                     if str(e["examiner_id"]) == str(examiner_id)), None)
    if examiner is None:
        raise ValueError("Choose an active external examiner whose appointment is current")
    try:
        cur = conn.execute("INSERT INTO module_external_examiners (module_code, examiner_id, "
                           "academic_year) VALUES (?, ?, ?)",
                           (code, examiner["examiner_id"], (academic_year or "").strip()))
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise ValueError(f"{examiner['name']} already examines {code}") from None
        raise
    spec._record(conn, code, {"external examiner": (None, examiner["name"])}, actor)
    return int(cur.lastrowid)


def unassign_examiner(conn, code, link_id, actor=None) -> bool:
    row = conn.execute("SELECT e.name FROM module_external_examiners me JOIN external_examiners e "
                       "ON e.examiner_id = me.examiner_id WHERE me.id = ? AND me.module_code = ?",
                       (link_id, code)).fetchone()
    if row is None:
        return False
    conn.execute("DELETE FROM module_external_examiners WHERE id = ?", (link_id,))
    spec._record(conn, code, {"external examiner": (row[0], None)}, actor)
    return True


# ── deliveries (course_sections) ────────────────────────────────────────


def term_choices(conn) -> list[dict]:
    return _dicts(conn.execute("SELECT id, name, academic_year, start_date, end_date "
                               "FROM academic_terms WHERE COALESCE(status, '') <> 'Superseded' "
                               "ORDER BY start_date, name"))


def deliveries(conn, code) -> list[dict]:
    from education_system.systems.university.services.bus.enrolment_bus import (
        ensure_section_column,
    )
    ensure_section_column(conn)
    return _dicts(conn.execute(
        "SELECT s.id, s.term_id, COALESCE(t.name, '') AS term, s.section_number, s.instructor, "
        "s.capacity, s.delivery_mode, s.location, s.status, "
        "(SELECT COUNT(*) FROM student_modules sm WHERE sm.section_id = s.id "
        "   AND sm.module_code = s.course_code AND sm.status = 'Enrolled') AS enrolled "
        "FROM course_sections s LEFT JOIN academic_terms t ON t.id = s.term_id "
        "WHERE s.course_code = ? ORDER BY t.start_date, s.section_number", (code,)))


def add_delivery(conn, code, term_id, capacity, instructor=None, delivery_mode="In Person",
                 location=None, actor=None) -> int:
    _require_module(conn, code)
    term = conn.execute("SELECT name FROM academic_terms WHERE id = ?", (term_id,)).fetchone()
    if term is None:
        raise ValueError("Choose a term")
    capacity = spec._number("capacity", capacity, integer=True, low=1)
    if not capacity:
        raise ValueError("A delivery needs a capacity of at least 1")
    if delivery_mode not in DELIVERY_MODES:
        raise ValueError(f"Mode must be one of: {', '.join(DELIVERY_MODES)}")
    n = conn.execute("SELECT COUNT(*) FROM course_sections WHERE course_code = ? AND term_id = ?",
                     (code, term_id)).fetchone()[0]
    number = f"{n + 1:03d}"
    cur = conn.execute("INSERT INTO course_sections (course_code, term_id, section_number, "
                       "instructor, capacity, delivery_mode, location, status) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, 'Open')",
                       (code, term_id, number, (instructor or "").strip(), capacity,
                        delivery_mode, (location or "").strip()))
    spec._record(conn, code, {"delivery": (None, f"{term[0]} section {number}, "
                                                 f"{capacity} places")}, actor)
    return int(cur.lastrowid)


def update_delivery(conn, code, section_id, *, capacity=None, status=None, actor=None):
    row = next((d for d in deliveries(conn, code) if d["id"] == int(section_id)), None)
    if row is None:
        raise ValueError("That delivery is not on this module")
    label = f"{row['term']} section {row['section_number']}"
    if capacity is not None:
        capacity = spec._number("capacity", capacity, integer=True, low=1)
        if capacity < row["enrolled"]:
            raise ValueError(f"{row['enrolled']} students are already enrolled on {label}")
        conn.execute("UPDATE course_sections SET capacity = ?, updated_at = datetime('now') "
                     "WHERE id = ?", (capacity, row["id"]))
        spec._record(conn, code, {f"delivery {label} capacity": (row["capacity"], capacity)}, actor)
    if status is not None:
        if status not in DELIVERY_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(DELIVERY_STATUSES)}")
        if status == "Cancelled" and row["enrolled"]:
            raise ValueError(f"Move the {row['enrolled']} enrolled student(s) off {label} "
                             "before cancelling it")
        conn.execute("UPDATE course_sections SET status = ?, updated_at = datetime('now') "
                     "WHERE id = ?", (status, row["id"]))
        spec._record(conn, code, {f"delivery {label} status": (row["status"], status)}, actor)


# ── timetable ───────────────────────────────────────────────────────────


def room_choices(conn) -> list[dict]:
    return _dicts(conn.execute(
        "SELECT id, TRIM(COALESCE(building, '') || ' ' || COALESCE(room_number, room_name, '')) "
        "AS label, capacity FROM rooms WHERE COALESCE(is_active, 1) = 1 ORDER BY label"))


def instructor_choices(conn) -> list[dict]:
    """``module_schedule.instructor_id`` points at ``instructors``, not ``users``."""
    return _dicts(conn.execute(
        "SELECT id, TRIM(first_name || ' ' || last_name) AS name FROM instructors "
        "WHERE COALESCE(is_active, 1) = 1 ORDER BY last_name, first_name"))


def slots(conn, code, include_cancelled=False) -> list[dict]:
    occurrences.ensure(conn)
    status = "" if include_cancelled else " AND COALESCE(ms.status, 'published') <> 'cancelled'"
    # db-audit: ignore[DBW001] - status is one of two literals
    return _dicts(conn.execute(
        "SELECT ms.id, ms.day_of_week, ms.start_time, ms.end_time, ms.session_type, "
        "ms.room_id, TRIM(COALESCE(r.building, '') || ' ' || COALESCE(r.room_number, "
        "r.room_name, '')) AS room, ms.instructor_id, TRIM(COALESCE(i.first_name, '') || ' ' || "
        "COALESCE(i.last_name, '')) AS instructor, ms.semester, ms.year, ms.status, "
        "ms.recurrence_until, ms.week_pattern, ms.online_url, ms.section_id, "
        "COALESCE(t.name || ' ' || cs.section_number, '') AS delivery FROM module_schedule ms "
        "LEFT JOIN rooms r ON r.id = ms.room_id LEFT JOIN instructors i ON i.id = ms.instructor_id "
        "LEFT JOIN course_sections cs ON cs.id = ms.section_id "
        "LEFT JOIN academic_terms t ON t.id = cs.term_id "
        f"WHERE ms.module_code = ?{status} ORDER BY CASE ms.day_of_week "
        + " ".join(f"WHEN '{d}' THEN {n}" for n, d in enumerate(DAYS))
        + " ELSE 9 END, ms.start_time", (code,)))


def slot_clashes(conn, day, start, end, room_id=None, instructor_id=None,
                 semester=None, exclude_id=None, module_code=None) -> list[str]:
    """Published slots on *day* overlapping start–end in the same room, with
    the same instructor, or of the same module (its students would have to be
    in two places — legitimate only for parallel groups, hence overridable).
    Slots in a different semester, when both give one, never clash."""
    clashes = []
    for row in conn.execute(
            "SELECT id, module_code, start_time, end_time, room_id, instructor_id, semester "
            "FROM module_schedule WHERE day_of_week = ? AND COALESCE(status, 'published') "
            "= 'published' AND start_time < ? AND end_time > ?", (day, end, start)):
        if exclude_id and row[0] == exclude_id:
            continue
        if semester and row[6] and str(row[6]).lower() != str(semester).lower():
            continue
        what = [w for w, same in (("room", room_id and row[4] == int(room_id)),
                                  ("instructor", instructor_id and row[5] == int(instructor_id)),
                                  ("same module", module_code and row[1] == module_code))
                if same]
        if what:
            clashes.append(f"{row[1]} {day} {row[2]}–{row[3]} ({' and '.join(what)})")
    return clashes


def _check_slot(day, start, end):
    if day not in DAYS:
        raise ValueError("Choose a day")
    for t in (start, end):
        if not _TIME.match(t or ""):
            raise ValueError("Times must be HH:MM, e.g. 09:00")
    if start >= end:
        raise ValueError("The session must end after it starts")


def _check_slot_extras(conn, code, section_id, week_pattern, online_url):
    if section_id and not conn.execute("SELECT 1 FROM course_sections WHERE id = ? "
                                       "AND course_code = ?", (section_id, code)).fetchone():
        raise ValueError(f"That delivery is not one of {code}'s")
    occurrences.parse_weeks(week_pattern)
    if online_url and not str(online_url).lower().startswith(("https://", "http://")):
        raise ValueError("The online link must start with https://")


def add_slot(conn, code, day, start, end, *, session_type="Lecture", room_id=None,
             instructor_id=None, semester=None, year=None, until=None, section_id=None,
             week_pattern=None, online_url=None, force=False, actor=None) -> dict:
    """Add a weekly slot. Raises ValueError listing clashes and warnings
    (room bookings, room size, staff hours / preferences) unless *force*.
    Returns ``{id, emails}``; send the emails once the change is committed."""
    _require_module(conn, code)
    occurrences.ensure(conn)
    _check_slot(day, start, end)
    _check_slot_extras(conn, code, section_id, week_pattern, online_url)
    problems = slot_clashes(conn, day, start, end, room_id, instructor_id, semester,
                            module_code=code)
    problems += occurrences.slot_warnings(conn, code, day, start, end, room_id,
                                          instructor_id and int(instructor_id), section_id)
    if problems and not force:
        raise ValueError("Clashes with: " + "; ".join(problems))
    cur = conn.execute(
        "INSERT INTO module_schedule (module_code, day_of_week, start_time, end_time, room_id, "
        "instructor_id, session_type, semester, year, status, recurrence, recurrence_until, "
        "section_id, week_pattern, online_url) VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(?, 'Fall'), "
        "COALESCE(?, 0), 'published', 'weekly', ?, ?, ?, ?)",
        (code, day, start, end, room_id or None, instructor_id or None, session_type,
         semester or None, int(year) if str(year or "").strip() else None, until or None,
         section_id or None, (week_pattern or "").replace(" ", "") or None, online_url or None))
    label = f"{day} {start}–{end} {session_type}"
    spec._record(conn, code, {"timetable": (None, label)}, actor)
    emails = occurrences.notify(conn, code, f"New {code} session",
                                f"A new weekly {session_type} for {code} has been added: "
                                f"{label}" + (f", weeks {week_pattern}" if week_pattern else "")
                                + (f"\nJoin online: {online_url}" if online_url else ""),
                                section_id=section_id or None,
                                instructor_id=instructor_id and int(instructor_id))
    return {"id": int(cur.lastrowid), "emails": emails}


def cancel_slot(conn, code, slot_id, actor=None) -> dict | None:
    """Stop a weekly slot from now on. Returns ``{emails}`` or None."""
    row = conn.execute("SELECT day_of_week, start_time, end_time, session_type, section_id, "
                       "instructor_id FROM module_schedule WHERE id = ? AND module_code = ? "
                       "AND COALESCE(status, 'published') <> 'cancelled'",
                       (slot_id, code)).fetchone()
    if row is None:
        return None
    conn.execute("UPDATE module_schedule SET status = 'cancelled', "
                 "modified_date = CURRENT_TIMESTAMP WHERE id = ?", (slot_id,))
    label = f"{row[0]} {row[1]}–{row[2]} {row[3]}"
    spec._record(conn, code, {"timetable": (label, None)}, actor)
    emails = occurrences.notify(conn, code, f"{code} session withdrawn",
                                f"The weekly {code} {label} session no longer runs.",
                                section_id=row[4], instructor_id=row[5])
    return {"emails": emails}


# ── student evaluation ──────────────────────────────────────────────────


def evaluations(conn, code) -> list[dict]:
    """Each evaluation run of the module with its response figures: Course
    Evaluation runs, plus the module survey for each year (its mean shown
    only once the anonymity threshold is met)."""
    try:
        runs = _dicts(conn.execute(
            "SELECT e.evaluation_id, e.academic_year, e.semester, e.response_count, "
            "e.completion_rate, e.start_date, e.end_date, "
            "(SELECT AVG(r.average_score) FROM evaluation_results r "
            "  WHERE r.evaluation_id = e.evaluation_id) AS mean_score, "
            "(SELECT MAX(q.scale_max) FROM evaluation_results r JOIN evaluation_questions q "
            "  ON q.question_id = r.question_id WHERE r.evaluation_id = e.evaluation_id) "
            "  AS scale_max FROM course_evaluations e "
            "WHERE e.module_code = ? AND e.deleted_at IS NULL "
            "ORDER BY e.academic_year DESC, e.semester", (code,)))
    except Exception as exc:
        if "no such" not in str(exc):
            raise
        runs = []
    from education_system.systems.university.application.evaluation import (
        module as module_evaluation,
    )
    for s in module_evaluation.module_summary(conn, code):
        runs.append({"evaluation_id": f"survey-{s['academic_year']}",
                     "academic_year": s["academic_year"], "semester": "Module survey",
                     "response_count": s["responses"],
                     "completion_rate": round(s["responses"] / s["invited"] * 100, 1)
                     if s["invited"] else 0,
                     "start_date": s["state"], "end_date": "",
                     "mean_score": s["overall"], "scale_max": 5 if s["overall"] else None})
    return runs


def you_said_we_did(conn, code) -> list[dict]:
    try:
        rows = _dicts(conn.execute(
            "SELECT y.theme, y.you_said, y.we_did, y.status, e.academic_year "
            "FROM evaluation_youssaid_wedid y JOIN course_evaluations e "
            "ON e.evaluation_id = y.evaluation_id WHERE e.module_code = ? "
            "ORDER BY y.created_at DESC", (code,)))
    except Exception as exc:
        if "no such" not in str(exc):
            raise
        rows = []
    from education_system.systems.university.application.evaluation import (
        module as module_evaluation,
    )
    for s in module_evaluation.module_summary(conn, code):
        rows += [{"theme": "Module survey", "you_said": r["you_said"], "we_did": r["we_did"],
                  "status": "published", "academic_year": s["academic_year"]}
                 for r in s["you_said_we_did"]]
    return rows


# ── filling missing credits and levels ──────────────────────────────────


def _programme_default(conn, course, cache):
    if course not in cache:
        from education_system.systems.university.domains.progression.domain.degree_audit.progress import (  # noqa: E501
            required_credits_for_course,
        )
        count = conn.execute("SELECT COUNT(*) FROM modules WHERE course = ? AND "
                             "COALESCE(module_code, '') <> '' AND COALESCE(is_active, 1) = 1",
                             (course,)).fetchone()[0]
        required = required_credits_for_course(conn, course, default=0)
        cache[course] = max(1, round(required / count)) if required and count else 0
    return cache[course]


def _level_for(year):
    try:
        y = int(str(year).strip())
    except (TypeError, ValueError):
        return None
    return y + 3 if 0 <= y <= 4 else None


def fill_plan(conn) -> list[dict]:
    """Active modules missing credits or a level, with what they would get."""
    ensure(conn)
    plan, cache = [], {}
    for code, course, credits, level, year in conn.execute(
            "SELECT module_code, course, credits, level, year FROM modules "
            "WHERE COALESCE(is_active, 1) = 1 AND TRIM(COALESCE(module_code, '')) <> '' "
            "AND (COALESCE(credits, 0) <= 0 OR level IS NULL) ORDER BY module_code").fetchall():
        changes = {}
        if not credits and course:
            value = _programme_default(conn, course, cache)
            if value:
                changes["credits"] = value
        if level is None and _level_for(year):
            changes["level"] = _level_for(year)
        if changes:
            plan.append({"module_code": code, "course": course, "year": year, **changes})
    return plan


def apply_fill(conn, plan, actor) -> int:
    """Apply :func:`fill_plan` rows through the change history."""
    done = 0
    for row in plan:
        changes = {k: row[k] for k in ("credits", "level") if k in row}
        if spec.apply_changes(conn, row["module_code"], changes, actor):
            done += 1
    return done
