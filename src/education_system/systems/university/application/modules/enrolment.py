"""Module enrolment rules: programme designations, exclusions, the module
waitlist, and enrolling one student or a whole cohort.

Enrolments are ``student_modules`` rows (``Enrolled`` / ``Withdrawn``); the
eligibility gate is ``services/bus/enrolment_bus.check_enrolment_eligibility``
(registration window, requisites, exclusions, capacity, sections). Everything
here goes through that gate, so the GUI, the CLI and the student catalogue
apply one set of rules.

* A **designation** says what a module is to a programme: core (must be
  passed), compulsory (must be taken) or optional, and in which year of study.
  A year of a full-time UK programme is 120 credits, so core + compulsory
  credits above 120, or fewer than 120 credits on offer, is reported.
* An **exclusion** says two modules overlap too much to both count — a
  student who has taken (or is taking) one cannot enrol on the other.
* The **waitlist** is FIFO. When a seat frees up the first waiting student
  who meets every other rule is enrolled; anyone blocked by something other
  than capacity stays waiting and is skipped, not dropped.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from datetime import datetime

from education_system.systems.university.infrastructure.database.schemas import (
    module_catalogue_schema as schema,
)
from education_system.systems.university.services.bus import enrolment_bus as gate

ENROLLED = "Enrolled"
WITHDRAWN = "Withdrawn"
YEAR_CREDITS = 120
#: Blocks a staff promotion from the waitlist is allowed to ignore: the seat
#: is being handed over, and the registration window is for self-service.
_PROMOTION_IGNORES = (gate.BLOCK_CAPACITY, gate.BLOCK_SECTION_CAPACITY, gate.BLOCK_WINDOW)


def ensure(conn):
    schema.apply_to_connection(conn)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _module_name(conn, code):
    row = conn.execute("SELECT module_name FROM modules WHERE module_code = ?", (code,)).fetchone()
    if row is None:
        raise ValueError(f"Module {code} does not exist")
    return row[0]


# ── designations ────────────────────────────────────────────────────────


def designations(conn, code) -> dict[str, dict]:
    """``{course_code: {category, year_of_study}}`` for the module."""
    ensure(conn)
    rows = _dicts(conn.execute("SELECT course_code, category, year_of_study "
                               "FROM module_programme_designations WHERE module_code = ?",
                               (code,)))
    return {r["course_code"]: r for r in rows}


def designations_for_course(conn, course_code) -> dict[str, dict]:
    """``{module_code: {category, year_of_study}}`` for one programme."""
    ensure(conn)
    rows = _dicts(conn.execute("SELECT module_code, category, year_of_study "
                               "FROM module_programme_designations WHERE course_code = ?",
                               (course_code,)))
    return {r["module_code"]: r for r in rows}


def set_designation(conn, code, course_code, category, year_of_study=None, actor=None):
    ensure(conn)
    category = (category or "").strip().lower()
    if category not in schema.DESIGNATIONS:
        raise ValueError(f"Designation must be one of: {', '.join(schema.DESIGNATIONS)}")
    year = int(year_of_study) if str(year_of_study or "").strip() else None
    if year is not None and not 0 <= year <= 7:
        raise ValueError("Year of study must be between 0 (foundation) and 7")
    _module_name(conn, code)
    conn.execute(
        "INSERT INTO module_programme_designations "
        "(course_code, module_code, category, year_of_study, updated_by, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(course_code, module_code) DO UPDATE SET "
        "category = excluded.category, year_of_study = excluded.year_of_study, "
        "updated_by = excluded.updated_by, updated_at = excluded.updated_at",
        (course_code, code, category, year, actor, _now()))
    return True


def clear_designation(conn, code, course_code) -> bool:
    ensure(conn)
    return conn.execute("DELETE FROM module_programme_designations "
                        "WHERE module_code = ? AND course_code = ?",
                        (code, course_code)).rowcount > 0


def programme_credit_issues(conn, course_code=None) -> list[str]:
    """Programme years whose designated modules do not make a 120-credit year."""
    ensure(conn)
    sql = ("SELECT d.course_code, d.year_of_study, "
           "SUM(CASE WHEN d.category IN ('core', 'compulsory') THEN COALESCE(m.credits, 0) "
           "ELSE 0 END), SUM(COALESCE(m.credits, 0)) "
           "FROM module_programme_designations d "
           "JOIN modules m ON m.module_code = d.module_code AND COALESCE(m.is_active, 1) = 1 "
           "WHERE d.year_of_study IS NOT NULL")
    params = []
    if course_code:
        sql += " AND d.course_code = ?"
        params.append(course_code)
    issues = []
    for course, year, required, offered in conn.execute(
            sql + " GROUP BY d.course_code, d.year_of_study", params):
        if required > YEAR_CREDITS:
            issues.append(f"{course} year {year}: core + compulsory modules are {required} "
                          f"credits, more than a {YEAR_CREDITS}-credit year")
        elif offered < YEAR_CREDITS:
            issues.append(f"{course} year {year}: only {offered} credits designated, "
                          f"a year needs {YEAR_CREDITS}")
    return issues


# ── exclusions ──────────────────────────────────────────────────────────


def exclusions(conn, code) -> list[dict]:
    """Rules involving *code*, in either direction, as ``{id, other, ...}``."""
    ensure(conn)
    return _dicts(conn.execute(
        "SELECT e.id, CASE WHEN e.module_code = ? THEN e.excluded_module_code "
        "ELSE e.module_code END AS other, COALESCE(m.module_name, '') AS other_name, "
        "e.reason, e.created_by, e.created_at FROM module_exclusions e "
        "LEFT JOIN modules m ON m.module_code = CASE WHEN e.module_code = ? "
        "THEN e.excluded_module_code ELSE e.module_code END "
        "WHERE ? IN (e.module_code, e.excluded_module_code) ORDER BY other",
        (code, code, code)))


def add_exclusion(conn, code, other, reason=None, actor=None) -> int:
    ensure(conn)
    other = (other or "").strip()
    if not other or other == code:
        raise ValueError("Choose a different module to exclude")
    for m in (code, other):
        _module_name(conn, m)
    if any(e["other"] == other for e in exclusions(conn, code)):
        raise ValueError(f"{code} and {other} already exclude each other")
    prereq = conn.execute(
        "SELECT 1 FROM degree_course_prerequisites WHERE (module_code = ? AND "
        "prerequisite_module_code = ?) OR (module_code = ? AND prerequisite_module_code = ?)",
        (code, other, other, code)).fetchone()
    if prereq:
        raise ValueError(f"One of {code} / {other} is a prerequisite of the other; "
                         "they cannot also exclude each other")
    cur = conn.execute("INSERT INTO module_exclusions (module_code, excluded_module_code, "
                       "reason, created_by) VALUES (?, ?, ?, ?)",
                       (code, other, (reason or "").strip() or None, actor))
    return int(cur.lastrowid)


def remove_exclusion(conn, rule_id) -> bool:
    ensure(conn)
    return conn.execute("DELETE FROM module_exclusions WHERE id = ?", (rule_id,)).rowcount > 0


# ── enrol / withdraw ────────────────────────────────────────────────────


def _section_term(conn, code, section_id):
    if section_id in (None, ""):
        return None
    row = conn.execute("SELECT t.name, t.academic_year FROM course_sections s "
                       "LEFT JOIN academic_terms t ON t.id = s.term_id "
                       "WHERE s.id = ? AND s.course_code = ?", (section_id, code)).fetchone()
    if row is None:
        raise ValueError(f"Section {section_id} is not a delivery of {code}")
    return row


def enrol(conn, code, student_id, section_id=None) -> str:
    """Enrol a student: ``'enrolled'``, ``'reinstated'`` or ``'already'``.

    ``student_modules`` is UNIQUE on (student, module), so a withdrawn student
    is reinstated rather than given a second row. Rules are the caller's to
    check (:func:`eligibility`) — staff may override them.
    """
    student_id = (str(student_id or "")).strip()
    if not conn.execute("SELECT 1 FROM students WHERE student_id = ?", (student_id,)).fetchone():
        raise ValueError(f"No student with ID {student_id}")
    name = _module_name(conn, code)
    ensure(conn)
    gate.ensure_section_column(conn)
    term = _section_term(conn, code, section_id)
    existing = conn.execute("SELECT status FROM student_modules WHERE student_id = ? "
                            "AND module_code = ?", (student_id, code)).fetchone()
    if existing and existing[0] == ENROLLED:
        return "already"
    today = datetime.now().strftime("%Y-%m-%d")
    # However they got the seat, they are no longer waiting for one.
    conn.execute("UPDATE module_waitlist SET status = 'enrolled', resolved_at = ?, "
                 "note = COALESCE(note, 'enrolled') WHERE module_code = ? AND student_id = ? "
                 "AND status = 'waiting'", (_now(), code, student_id))
    values = {"status": ENROLLED, "enrollment_date": today, "section_id": section_id}
    if term:
        values.update(semester=term[0], year=term[1])
    columns = {r[1] for r in conn.execute("PRAGMA table_info(student_modules)")}
    values = {k: v for k, v in values.items() if k in columns}
    if existing:
        sets = ", ".join(f"{k} = ?" for k in values)
        # db-audit: ignore[DBW001] - keys are literals filtered by PRAGMA
        conn.execute(f"UPDATE student_modules SET {sets} WHERE student_id = ? AND module_code = ?",
                     (*values.values(), student_id, code))
        return "reinstated"
    values.update(student_id=student_id, module_code=code, module_name=name)
    # db-audit: ignore[DBW001] - keys are literals filtered by PRAGMA
    conn.execute(f"INSERT INTO student_modules ({', '.join(values)}) "
                 f"VALUES ({', '.join('?' for _ in values)})", tuple(values.values()))
    return "enrolled"


def withdraw(conn, code, student_id) -> bool:
    """Mark an enrolment withdrawn. The row and any grade are kept."""
    return conn.execute("UPDATE student_modules SET status = ? WHERE student_id = ? "
                        "AND module_code = ? AND status = ?",
                        (WITHDRAWN, student_id, code, ENROLLED)).rowcount > 0


def eligibility(conn, code, student_id, section_id=None):
    return gate.check_enrolment_eligibility(student_id, code, section_id=section_id, conn=conn)


# ── waitlist ────────────────────────────────────────────────────────────


def waitlist(conn, code, include_resolved=False) -> list[dict]:
    ensure(conn)
    status = "" if include_resolved else " AND w.status = 'waiting'"
    # db-audit: ignore[DBW001] - status is one of two literals
    return _dicts(conn.execute(
        "SELECT w.id, w.student_id, TRIM(COALESCE(s.first_name, '') || ' ' || "
        "COALESCE(s.last_name, '')) AS name, w.section_id, w.position, w.status, w.added_at, "
        "w.resolved_at, w.resolved_by, w.note FROM module_waitlist w "
        f"LEFT JOIN students s ON s.student_id = w.student_id WHERE w.module_code = ?{status} "
        "ORDER BY CASE w.status WHEN 'waiting' THEN 0 ELSE 1 END, w.position", (code,)))


def join_waitlist(conn, code, student_id, section_id=None) -> int:
    """Queue a student for a full module. Returns their position."""
    ensure(conn)
    student_id = str(student_id or "").strip()
    _module_name(conn, code)
    if not conn.execute("SELECT 1 FROM students WHERE student_id = ?", (student_id,)).fetchone():
        raise ValueError(f"No student with ID {student_id}")
    if conn.execute("SELECT 1 FROM student_modules WHERE student_id = ? AND module_code = ? "
                    "AND status = ?", (student_id, code, ENROLLED)).fetchone():
        raise ValueError(f"{student_id} is already enrolled on {code}")
    row = conn.execute("SELECT position FROM module_waitlist WHERE module_code = ? "
                       "AND student_id = ? AND status = 'waiting'", (code, student_id)).fetchone()
    if row:
        raise ValueError(f"{student_id} is already on the {code} waitlist at position {row[0]}")
    position = conn.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM module_waitlist "
                            "WHERE module_code = ? AND status = 'waiting'", (code,)).fetchone()[0]
    conn.execute("INSERT INTO module_waitlist (module_code, student_id, section_id, position) "
                 "VALUES (?, ?, ?, ?)", (code, student_id, section_id, position))
    return int(position)


def _resolve(conn, entry_id, status, actor, note=None):
    conn.execute("UPDATE module_waitlist SET status = ?, resolved_at = ?, resolved_by = ?, "
                 "note = COALESCE(?, note) WHERE id = ?", (status, _now(), actor, note, entry_id))


def remove_from_waitlist(conn, entry_id, actor, note=None) -> bool:
    ensure(conn)
    row = conn.execute("SELECT status FROM module_waitlist WHERE id = ?", (entry_id,)).fetchone()
    if not row or row[0] != "waiting":
        return False
    _resolve(conn, entry_id, "removed", actor, note)
    return True


def _seat_free(conn, code, section_id):
    cap = gate.module_capacity(conn, code)
    if cap is not None and gate.enrolled_count(conn, code) >= cap:
        return False
    if section_id in (None, ""):
        return True
    section = next((s for s in gate.sections_for_module(conn, code)
                    if str(s["id"]) == str(section_id)), None)
    return section is not None and not section["full"]


def promote_next(conn, code, actor) -> dict | None:
    """Enrol the first waiting student who meets every rule but capacity.

    Returns ``{student_id, skipped: [(student_id, reason)]}`` or None when no
    seat is free or nobody waiting can take it.
    """
    skipped = []
    for entry in waitlist(conn, code):
        if not _seat_free(conn, code, entry["section_id"]):
            continue
        result = eligibility(conn, code, entry["student_id"], entry["section_id"])
        blocks = [b for b in result.blocks if b.kind not in _PROMOTION_IGNORES]
        if blocks:
            skipped.append((entry["student_id"], "; ".join(b.message for b in blocks)))
            continue
        _resolve(conn, entry["id"], "enrolled", actor, "promoted when a seat came free")
        enrol(conn, code, entry["student_id"], entry["section_id"])
        return {"student_id": entry["student_id"], "skipped": skipped}
    return None


def promote_all(conn, code, actor) -> list[str]:
    """Fill every free seat from the waitlist. Returns who was enrolled."""
    enrolled = []
    while True:
        promoted = promote_next(conn, code, actor)
        if not promoted:
            return enrolled
        enrolled.append(promoted["student_id"])


def enrol_from_waitlist(conn, code, entry_id, actor) -> str:
    """Staff choose a waiting student directly (an override of the order)."""
    row = conn.execute("SELECT student_id, section_id, status FROM module_waitlist "
                       "WHERE id = ? AND module_code = ?", (entry_id, code)).fetchone()
    if not row or row[2] != "waiting":
        raise ValueError("That student is no longer waiting")
    _resolve(conn, entry_id, "enrolled", actor, "enrolled by staff from the waitlist")
    return enrol(conn, code, row[0], row[1])


# ── cohorts ─────────────────────────────────────────────────────────────


def cohort(conn, course_code, year_of_study=None) -> list[dict]:
    """Active students on a programme (by code or by its name), optionally one year."""
    names = [course_code] + [r[0] for r in conn.execute(
        "SELECT COALESCE(NULLIF(course_name, ''), name) FROM courses "
        "WHERE COALESCE(NULLIF(course_code, ''), code) = ?", (course_code,)) if r[0]]
    marks = ", ".join("?" for _ in names)
    sql = ("SELECT student_id, TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) "
           "AS name, COALESCE(year_of_study, year) AS year_of_study FROM students "
           f"WHERE (course IN ({marks}) OR program IN ({marks})) "
           "AND COALESCE(is_active, 1) = 1 AND LOWER(COALESCE(status, 'active')) "
           "NOT IN ('withdrawn', 'graduated', 'inactive', 'suspended')")
    params = names + names
    if str(year_of_study or "").strip():
        sql += " AND COALESCE(year_of_study, year) = ?"
        params.append(int(year_of_study))
    # db-audit: ignore[DBW001] - only placeholders are interpolated
    return _dicts(conn.execute(sql + " ORDER BY student_id", params))


def _bulk_one(conn, code, sid, section_id, override, waitlist_full, out):
    result = eligibility(conn, code, sid, section_id)
    if result.blocks and not override:
        if waitlist_full and result.only_capacity:
            try:
                out["waitlisted"].append((sid, join_waitlist(conn, code, sid, section_id)))
            except ValueError as exc:
                out["blocked"].append((sid, str(exc)))
            return
        out["blocked"].append((sid, result.reason()))
        return
    outcome = enrol(conn, code, sid, section_id)
    out["already" if outcome == "already" else "enrolled"].append(sid)
    if result.blocks:
        out["overridden"].append((sid, result.reason()))


def bulk_enrol(conn, code, student_ids, section_id=None, *, override=False,
               waitlist_full=True) -> dict:
    """Enrol many students through the gate.

    Students the rules block are reported, not enrolled, unless *override*;
    when capacity is the only block they join the waitlist (*waitlist_full*).
    """
    out = {"enrolled": [], "already": [], "blocked": [], "waitlisted": [], "overridden": []}
    for sid in dict.fromkeys(str(s).strip() for s in student_ids if str(s).strip()):
        _bulk_one(conn, code, sid, section_id, override, waitlist_full, out)
    return out


def bulk_withdraw(conn, code, student_ids, actor) -> dict:
    """Withdraw several students, then fill the freed seats from the waitlist."""
    withdrawn = [sid for sid in student_ids if withdraw(conn, code, sid)]
    return {"withdrawn": withdrawn, "promoted": promote_all(conn, code, actor) if withdrawn else []}
