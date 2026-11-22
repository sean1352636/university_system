"""What the study companion knows about a student, read from the records
that already hold it.

The companion used to know nothing outside its own four tables: plans were
built without the exam timetable, deadlines, marks or the student's other
plans, and the exam date was guessed by matching a module code against
calendar event titles. Everything here is read-only and comes from:

* enrolments — ``student_modules`` (status Enrolled);
* exams — the published exam timetable (``exams``, ``status = 'published'``;
  the sitting's own candidate list, else the module's enrolments, as
  ``exam_results.roster`` does);
* deadlines — ``assignments`` on the student's modules that they have not
  yet made a final submission for;
* marks — **released** marks only: confirmed / ratified / locked
  ``module_grades`` rows and assignment grades with ``grade_released_at``.
  A provisional mark never shapes a plan, so a plan cannot leak one;
* topics — the module specification's indicative content, the module's
  learning outcomes and its catalogue description;
* the student's own flashcard accuracy and study-session ratings.

Functions take an open connection and never write. A database without one
of these tables (a fresh test database, say) simply contributes nothing.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta

STAFF_ROLES = frozenset({
    "admin", "administrator", "superadmin", "staff", "instructor", "lecturer",
    "teacher", "faculty",
})
ADMIN_ROLES = frozenset({"admin", "administrator", "superadmin"})
RELEASED_STATUSES = ("confirmed", "ratified", "final", "published", "released")
WEAK_MARK = 50.0
WEAK_ACCURACY = 60.0


# ── identity ────────────────────────────────────────────────────────────


def owner_id(user) -> str | None:
    """The id a signed-in user's companion rows are owned by.

    A student's rows key on their student number (``current_user['student_id']``,
    resolved from ``users`` at sign-in), not ``current_user['id']`` — that is
    the ``users`` row id, which the GUI used to pass and which matches no
    enrolment, mark or exam. Staff have no student record and use their
    username.
    """
    if not user:
        return None
    if not isinstance(user, dict):
        user = getattr(user, "__dict__", {}) or {}
    value = user.get("student_id") or user.get("username")
    return str(value) if value else None


def owner_for_subject(conn, subject, claimed_student_id=None) -> str | None:
    """:func:`owner_id` for an API caller: ``users.student_id`` for the token's
    username, else the token's ``student_id`` claim, else the username."""
    if not subject:
        return None
    try:
        row = conn.execute("SELECT student_id FROM users WHERE username = ?",
                           (str(subject),)).fetchone()
    except Exception:
        row = None
    if row and row[0]:
        return str(row[0])
    return str(claimed_student_id or subject)


def role_of(user) -> str:
    if not user:
        return ""
    if not isinstance(user, dict):
        user = getattr(user, "__dict__", {}) or {}
    return str(user.get("role") or "").strip().lower()


def is_staff(user) -> bool:
    return role_of(user) in STAFF_ROLES


def is_student_record(conn, student_id) -> bool:
    if not _has_table(conn, "students"):
        return False
    return conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                        (str(student_id),)).fetchone() is not None


# ── helpers ─────────────────────────────────────────────────────────────


def _has_table(conn, name) -> bool:
    try:
        return conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') "
                            "AND name = ?", (name,)).fetchone() is not None
    except Exception:
        return False


def _columns(conn, table) -> set:
    try:
        return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}
    except Exception:
        return set()


def _dicts(cur) -> list[dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def enrolled_condition(conn, alias="sm") -> str:
    """SQL that keeps only current enrolments (``status`` Enrolled, or every
    row on a database whose ``student_modules`` has no status)."""
    if "status" in _columns(conn, "student_modules"):
        return f"LOWER(COALESCE({alias}.status, 'enrolled')) = 'enrolled'"
    return "1 = 1"


def _iso(value) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


# ── enrolments and marks ────────────────────────────────────────────────


def enrolled_modules(conn, student_id) -> list[dict]:
    """``[{module_code, module_name}]`` the student is enrolled on."""
    if not _has_table(conn, "student_modules"):
        return []
    has_modules = _has_table(conn, "modules")
    names = ["m.module_name"] if has_modules else []
    if "module_name" in _columns(conn, "student_modules"):
        names.append("sm.module_name")
    sql = ("SELECT sm.module_code, COALESCE(" + ", ".join(names + ["sm.module_code"]) + ") "
           "AS module_name FROM student_modules sm "
           + ("LEFT JOIN modules m ON m.module_code = sm.module_code " if has_modules else "")
           + "WHERE sm.student_id = ? AND " + enrolled_condition(conn) + " ORDER BY sm.module_code")
    return _dicts(conn.execute(sql, (str(student_id),)))


def module_name(conn, code) -> str:
    if code and _has_table(conn, "modules"):
        row = conn.execute("SELECT module_name FROM modules WHERE module_code = ?",
                           (code,)).fetchone()
        if row and row[0]:
            return str(row[0])
    return str(code or "")


def released_marks(conn, student_id) -> dict[str, float]:
    """``{module_code: percentage}`` from marks the student has been given.

    Module results count once confirmed, ratified or locked; assignment
    grades once released. Unreleased marks are ignored entirely.
    """
    marks: dict[str, list[float]] = {}
    sid = str(student_id)
    if _has_table(conn, "module_grades"):
        cols = _columns(conn, "module_grades")
        cond = ["final_score IS NOT NULL"]
        released = []
        if "status" in cols:
            released.append("LOWER(COALESCE(status, '')) IN ("
                            + ", ".join("?" * len(RELEASED_STATUSES)) + ")")
        if "locked" in cols:
            released.append("COALESCE(locked, 0) = 1")
        if released:
            cond.append("(" + " OR ".join(released) + ")")
            params = [sid, *(RELEASED_STATUSES if "status" in cols else ())]
            for code, score in conn.execute(
                    "SELECT module_code, final_score FROM module_grades WHERE student_id = ? AND "
                    + " AND ".join(cond), params).fetchall():
                marks.setdefault(code, []).append(float(score))
    if _has_table(conn, "assignment_submissions") and _has_table(conn, "assignments"):
        if "grade_released_at" in _columns(conn, "assignment_submissions"):
            a_cols = _columns(conn, "assignments")
            out_of = ("COALESCE(NULLIF(a.max_score, 0), NULLIF(a.max_marks, 0), 100)"
                      if "max_score" in a_cols else "COALESCE(NULLIF(a.max_marks, 0), 100)")
            for code, pct in conn.execute(
                    "SELECT a.module_code, 100.0 * s.grade / " + out_of + " "
                    "FROM assignment_submissions s JOIN assignments a ON a.id = s.assignment_id "
                    "WHERE s.student_id = ? AND s.grade IS NOT NULL "
                    "AND s.grade_released_at IS NOT NULL", (sid,)).fetchall():
                if pct is not None:
                    marks.setdefault(code, []).append(float(pct))
    return {code: round(sum(v) / len(v), 1) for code, v in marks.items() if v}


def card_accuracy(conn, student_id) -> dict[str, float]:
    """``{module_code: % recalled}`` over the student's own flashcards."""
    if not _has_table(conn, "flashcards"):
        return {}
    rows = conn.execute(
        "SELECT course_id, SUM(correct_count), SUM(review_count) FROM flashcards "
        "WHERE student_id = ? AND course_id IS NOT NULL AND course_id <> '' "
        "GROUP BY course_id", (str(student_id),)).fetchall()
    return {r[0]: round(100.0 * (r[1] or 0) / r[2], 1) for r in rows if r[2]}


def session_ratings(conn, student_id) -> dict[str, float]:
    """``{module_code: average self-rated effectiveness (1–5)}``."""
    if not _has_table(conn, "study_sessions"):
        return {}
    rows = conn.execute(
        "SELECT module_code, AVG(effectiveness_rating) FROM study_sessions "
        "WHERE student_id = ? AND module_code IS NOT NULL "
        "AND effectiveness_rating IS NOT NULL GROUP BY module_code",
        (str(student_id),)).fetchall()
    return {r[0]: round(float(r[1]), 2) for r in rows if r[1] is not None}


def weak_modules(conn, student_id) -> list[dict]:
    """Modules that need more time, weakest first, each with its reasons.

    A module is weak when a released mark is under 50%, flashcard recall is
    under 60%, or the student rates their sessions on it below 3/5.
    """
    marks = released_marks(conn, student_id)
    recall = card_accuracy(conn, student_id)
    ratings = session_ratings(conn, student_id)
    out = []
    for code in sorted(set(marks) | set(recall) | set(ratings)):
        reasons, weight = [], 0.0
        if code in marks and marks[code] < WEAK_MARK:
            reasons.append(f"released marks average {marks[code]:.0f}%")
            weight += (WEAK_MARK - marks[code]) / 10 + 1
        if code in recall and recall[code] < WEAK_ACCURACY:
            reasons.append(f"flashcard recall {recall[code]:.0f}%")
            weight += (WEAK_ACCURACY - recall[code]) / 20 + 0.5
        if code in ratings and ratings[code] < 3:
            reasons.append(f"sessions rated {ratings[code]:.1f}/5")
            weight += 3 - ratings[code]
        if reasons:
            out.append({"module_code": code, "reasons": reasons, "weight": round(weight, 2)})
    out.sort(key=lambda r: -r["weight"])
    return out


# ── exams and deadlines ─────────────────────────────────────────────────


def _roster(exam) -> list[str] | None:
    """The sitting's own candidate list, or ``None`` when it has none (then
    every student enrolled on the module sits it)."""
    raw = exam.get("enrolled_student_ids")
    try:
        ids = [str(s) for s in (json.loads(raw) if isinstance(raw, str) else raw or [])]
    except (TypeError, ValueError):
        ids = []
    return ids or None


def upcoming_exams(conn, student_id, start=None, end=None) -> list[dict]:
    """Published exam sittings the student is down for, from ``start``
    (default today) to ``end`` (default a year on), in date order."""
    if not _has_table(conn, "exams"):
        return []
    start = _iso(start or date.today())
    end = _iso(end or (date.fromisoformat(start) + timedelta(days=366)))
    sid = str(student_id)
    enrolled = {m["module_code"] for m in enrolled_modules(conn, sid)}
    cols = _columns(conn, "exams")
    status = "COALESCE(status, 'published') = 'published' AND " if "status" in cols else ""
    out = []
    for exam in _dicts(conn.execute(
            "SELECT * FROM exams WHERE " + status + "date BETWEEN ? AND ? "
            "ORDER BY date, start_time", (start, end))):
        ids = _roster(exam)
        if (sid in ids) if ids else (exam.get("module_code") in enrolled):
            out.append({
                "exam_id": exam.get("id"),
                "module_code": exam.get("module_code"),
                "module_name": exam.get("module_name") or module_name(conn, exam.get("module_code")),
                "name": exam.get("exam_name") or f"{exam.get('module_code')} exam",
                "date": str(exam.get("date"))[:10],
                "start_time": exam.get("start_time"),
                "end_time": exam.get("end_time"),
                "room": exam.get("room"),
            })
    return out


def next_exam(conn, student_id, module_code, today=None) -> dict | None:
    """The student's next published sitting for ``module_code``."""
    for exam in upcoming_exams(conn, student_id, today):
        if exam["module_code"] == module_code:
            return exam
    return None


def upcoming_deadlines(conn, student_id, start=None, end=None) -> list[dict]:
    """Assignment deadlines on the student's modules, ``start``..``end``
    inclusive, that they have not made a final submission for."""
    if not (_has_table(conn, "assignments") and _has_table(conn, "student_modules")):
        return []
    start = _iso(start or date.today())
    end = _iso(end or (date.fromisoformat(start) + timedelta(days=366)))
    cols = _columns(conn, "assignments")
    cond = ["sm.student_id = ?", enrolled_condition(conn), "date(a.due_date) BETWEEN ? AND ?"]
    if "is_active" in cols:
        cond.append("COALESCE(a.is_active, 1) = 1")
    if "archived" in cols:
        cond.append("COALESCE(a.archived, 0) = 0")
    if "status" in cols:
        cond.append("LOWER(COALESCE(a.status, 'active')) NOT IN ('draft', 'archived', 'cancelled')")
    sql = ("SELECT a.id AS assignment_id, a.module_code, a.title, a.due_date "
           "FROM assignments a JOIN student_modules sm ON sm.module_code = a.module_code "
           "WHERE " + " AND ".join(cond))
    if _has_table(conn, "assignment_submissions"):
        final = ("AND COALESCE(s.is_final_submission, 1) = 1 "
                 if "is_final_submission" in _columns(conn, "assignment_submissions") else "")
        sql += (" AND NOT EXISTS (SELECT 1 FROM assignment_submissions s WHERE "
                "s.assignment_id = a.id AND s.student_id = sm.student_id " + final + ")")
    sql += " ORDER BY a.due_date"
    return _dicts(conn.execute(sql, (str(student_id), start, end)))


# ── topics ──────────────────────────────────────────────────────────────

_SPLIT = re.compile(r"[\n;•]+|(?<=[.!?])\s+")


def _pieces(text) -> list[str]:
    out = []
    for piece in _SPLIT.split(str(text or "")):
        piece = re.sub(r"^\s*(?:[-*\d.)(]+\s*)", "", piece).strip(" .,:-\t")
        if 3 <= len(piece) <= 140:
            out.append(piece)
    return out


def module_topics(conn, code, limit=12) -> list[str]:
    """Topics to study for a module, from its specification's indicative
    content, its learning outcomes and its catalogue description."""
    if not code:
        return []
    topics: list[str] = []
    if _has_table(conn, "module_specifications"):
        row = conn.execute("SELECT indicative_content FROM module_specifications "
                           "WHERE module_code = ?", (code,)).fetchone()
        if row and row[0]:
            topics += _pieces(row[0])
    if _has_table(conn, "learning_outcomes") and "module_code" in _columns(conn, "learning_outcomes"):
        topics += [str(r[0]).strip() for r in conn.execute(
            "SELECT description FROM learning_outcomes WHERE module_code = ? "
            "ORDER BY rowid", (code,)).fetchall() if r[0]]
    if not topics and "description" in _columns(conn, "modules"):
        row = conn.execute("SELECT description FROM modules WHERE module_code = ?",
                           (code,)).fetchone()
        if row and row[0]:
            topics += _pieces(row[0])
    seen, unique = set(), []
    for t in topics:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            unique.append(t)
    return unique[:limit]


def course_material(conn, code, concept=None) -> dict:
    """What the course records say about a module (and, when given, the
    passages that mention ``concept``) — the grounding for explanations."""
    out = {"module_code": code, "module_name": module_name(conn, code) if code else "",
           "aims": "", "description": "", "topics": module_topics(conn, code, 20),
           "mentions": []}
    if code and _has_table(conn, "module_specifications"):
        row = conn.execute("SELECT aims, reading_list FROM module_specifications "
                           "WHERE module_code = ?", (code,)).fetchone()
        if row:
            out["aims"] = row[0] or ""
            out["reading_list"] = row[1] or ""
    if code and "description" in _columns(conn, "modules"):
        row = conn.execute("SELECT description FROM modules WHERE module_code = ?",
                           (code,)).fetchone()
        if row:
            out["description"] = row[0] or ""
    if concept:
        needle = concept.lower()
        texts = out["topics"] + _pieces(out["aims"]) + _pieces(out["description"])
        out["mentions"] = [t for t in texts if needle in t.lower()][:6]
    return out


# ── load already planned ────────────────────────────────────────────────


def planned_minutes(conn, student_id, start, end, exclude_plan=None) -> dict[str, int]:
    """``{date: minutes}`` already scheduled by the student's other active
    plans, so a new plan does not double-book the same evenings."""
    if not _has_table(conn, "study_plan_tasks"):
        return {}
    params = [str(student_id), _iso(start), _iso(end)]
    extra = ""
    if exclude_plan is not None:
        extra = " AND p.plan_id <> ?"
        params.append(int(exclude_plan))
    rows = conn.execute(
        "SELECT t.scheduled_date, SUM(COALESCE(t.duration_minutes, 0)) "
        "FROM study_plan_tasks t JOIN study_plans p ON p.plan_id = t.plan_id "
        "WHERE p.student_id = ? AND COALESCE(p.status, 'Active') = 'Active' "
        "AND COALESCE(t.status, 'pending') = 'pending' "
        "AND t.scheduled_date BETWEEN ? AND ?" + extra +
        " GROUP BY t.scheduled_date", params).fetchall()
    return {str(r[0])[:10]: int(r[1] or 0) for r in rows}
