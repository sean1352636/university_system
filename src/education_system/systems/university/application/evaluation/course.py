"""Course evaluation: the students on a course (programme) rate the course as
a whole once a year. One rule set behind the Course Evaluation window, its
CLI menu and the Course Management evaluation tab.

* **One survey per course and academic year** on ``course_evaluations``
  (``course_code`` set). Opening it freezes a copy of the chosen template
  (plus the institution's required questions, an overall question and a
  comments box) so later template edits cannot change what was asked.
* **Window:** open from ``opens_at`` to ``closes_at`` (by default the last
  three weeks of the current term); staff can close it early.
* **Eligibility:** only active students filed under the course
  (``students.course`` holds its code or name) are invited and may answer,
  once each. Who answered is kept only on the invitation; the response
  carries a random token and the day.
* **Who sees results:** the course leader, the course team (including the
  leaders of the course's modules) and admins - and nobody until
  ``min_responses`` students have answered. Comments that look abusive or
  identifying wait for an admin to release them.
* **Closing the loop:** once closed, the leader writes a response (what the
  results said, actions, "you said, we did") and publishes it to every
  invited student.

Functions take an open connection and do not commit; the caller does.
Returned ``emails`` are ``(address, subject, body)`` for the caller to send
after committing.
"""

from __future__ import annotations

import csv
import json
import secrets
from datetime import date, datetime, timedelta

from education_system.systems.university.application.evaluation import module as module_evaluation
from education_system.systems.university.application.programmes.course_team import (  # noqa: F401
    access,
    course,
    course_for_student,
    courses,
    leader,
    remove_team_member,
    set_team_member,
    students_on,
    team,
)
from education_system.systems.university.application.programmes.course_team import (
    _names,
    _require_leader,
)
from education_system.systems.university.application.evaluation.teaching_history import (  # noqa: F401
    instructor_history,
    refresh_instructor_history,
)
from education_system.systems.university.infrastructure.database.schemas import (
    course_evaluation_schema as schema,
)

WINDOW_DAYS = 21
REMIND_EVERY_DAYS = 3
MIN_THRESHOLD = 3
DEFAULT_TEMPLATE = "Student Form (auto)"
DEFAULT_CRITERIA = ("Teaching quality", "Course content", "Workload", "Communication",
                    "Overall")
OVERALL = "Overall, I am satisfied with the quality of my course."
COMMENTS = "Is there anything else you would like to tell us about your course?"
SURVEY_TYPE = "course_survey"
NUMERIC = ("rating", "likert", "scale")
_QUESTION_COPY = ("question_text", "question_type", "question_category", "is_required",
                  "scale_min", "scale_max", "options", "options_json", "bank_id",
                  "show_if_value", "show_if_op", "aria_label")


def ensure(conn):
    schema.apply_to_connection(conn)


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _one(conn, sql, params=()):
    rows = _dicts(conn.execute(sql, params))
    return rows[0] if rows else None


def _now(now=None):
    return now or datetime.now()


def _columns(conn, table):
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}


# ── templates and the frozen question set ───────────────────────────────


def templates(conn) -> list[dict]:
    """Templates staff can base a course survey on."""
    deleted = " AND deleted_at IS NULL" if "deleted_at" in _columns(
        conn, "evaluation_templates") else ""
    # db-audit: ignore[DBW001] - literal clause only
    return _dicts(conn.execute(
        f"SELECT template_id, template_name, template_type, is_default FROM evaluation_templates "
        f"WHERE COALESCE(is_active, 1) = 1 AND COALESCE(template_type, '') <> ?{deleted} "
        f"ORDER BY is_default DESC, template_name", (SURVEY_TYPE,)))


def default_template(conn) -> int:
    """The default template, else the standard five-criterion student form
    (created when missing)."""
    for t in templates(conn):
        if t["is_default"]:
            return t["template_id"]
    row = conn.execute("SELECT template_id FROM evaluation_templates WHERE template_name = ?",
                       (DEFAULT_TEMPLATE,)).fetchone()
    if row:
        return row[0]
    tid = conn.execute("INSERT INTO evaluation_templates (template_name, template_type, "
                       "description, is_active) VALUES (?, 'student', ?, 1)",
                       (DEFAULT_TEMPLATE, "Standard course survey")).lastrowid
    for order, text in enumerate(DEFAULT_CRITERIA, 1):
        conn.execute("INSERT INTO evaluation_questions (template_id, question_text, "
                     "question_type, question_category, is_required, scale_min, scale_max, "
                     "display_order) VALUES (?, ?, 'rating', ?, 1, 1, 5, ?)",
                     (tid, text, "overall" if text == "Overall" else "course", order))
    return tid


def _is_numeric(q):
    return str(q.get("question_type") or "").lower() in NUMERIC


def is_overall(q) -> bool:
    return _is_numeric(q) and ("overall" in str(q.get("question_category") or "").lower()
                               or "overall" in str(q.get("question_text") or "").lower())


def _source_questions(conn, template_id):
    cols = _columns(conn, "evaluation_questions")
    keep = [c for c in ("question_id", "parent_question_id") + _QUESTION_COPY if c in cols]
    return _dicts(conn.execute(f"SELECT {', '.join(keep)} FROM evaluation_questions WHERE "
                               f"template_id = ? ORDER BY display_order, question_id",
                               (template_id,)))


def _extra_questions(conn, existing):
    texts = {q["question_text"].strip().lower() for q in existing}
    extra = [{"question_text": b["question_text"], "question_category": "institution",
              "question_type": "text" if b["question_type"] == "text" else "likert",
              "is_required": 0 if b["question_type"] == "text" else 1, "scale_min": 1,
              "scale_max": 5} for b in module_evaluation.required_bank(conn)
             if b["question_text"].strip().lower() not in texts]
    if not any(is_overall(q) for q in existing):
        extra.append({"question_text": OVERALL, "question_type": "rating",
                      "question_category": "overall", "is_required": 1, "scale_min": 1,
                      "scale_max": 5})
    if not any(str(q.get("question_type") or "").lower() == "text" for q in existing):
        extra.append({"question_text": COMMENTS, "question_type": "text",
                      "question_category": "comments", "is_required": 0})
    return extra


def _freeze(conn, template_id, label, actor):
    """Copy the template (plus required, overall and comments questions)
    into a survey-only template and return its id."""
    source = _source_questions(conn, template_id)
    if not source:
        raise ValueError("That template has no questions")
    copy_id = conn.execute("INSERT INTO evaluation_templates (template_name, template_type, "
                           "description, created_by, is_active) VALUES (?, ?, ?, ?, 0)",
                           (label, SURVEY_TYPE, f"Frozen from template {template_id}",
                            actor)).lastrowid
    cols = [c for c in _QUESTION_COPY if c in _columns(conn, "evaluation_questions")]
    mapping = {}
    for order, q in enumerate(source + _extra_questions(conn, source), 1):
        values = [q.get(c) for c in cols]
        new_id = conn.execute(
            f"INSERT INTO evaluation_questions (template_id, display_order, {', '.join(cols)}) "
            f"VALUES (?, ?, {', '.join('?' for _ in cols)})",
            (copy_id, order, *values)).lastrowid
        if q.get("question_id"):
            mapping[q["question_id"]] = new_id
    for q in source:
        if q.get("parent_question_id") in mapping:
            conn.execute("UPDATE evaluation_questions SET parent_question_id = ? WHERE "
                         "question_id = ?", (mapping[q["parent_question_id"]],
                                             mapping[q["question_id"]]))
    return copy_id


def questions(conn, evaluation_id) -> list[dict]:
    s = survey(conn, evaluation_id)
    out = []
    for q in _source_questions(conn, s["template_id"]):
        q["question_type"] = str(q.get("question_type") or "rating").lower()
        q["choices"] = _choices(q)
        q["scale_min"] = q.get("scale_min") or 1
        q["scale_max"] = q.get("scale_max") or 5
        out.append(q)
    return out


def _choices(q):
    if q["question_type"] == "yes/no":
        return ["Yes", "No"]
    for key in ("options_json", "options"):
        raw = q.get(key)
        if not raw:
            continue
        try:
            values = json.loads(raw)
        except (TypeError, ValueError):
            values = [v.strip() for v in str(raw).split(",")]
        if isinstance(values, list) and values:
            return [str(v) for v in values if str(v).strip()]
    return []


def should_show(q, answers) -> bool:
    """Branching: a question with a parent shows only when the parent's
    answer meets ``show_if_op`` / ``show_if_value``."""
    parent = q.get("parent_question_id")
    if not parent:
        return True
    given, target = answers.get(parent), q.get("show_if_value")
    if given is None:
        return False
    op = q.get("show_if_op") or "eq"
    if op in ("gt", "lt"):
        try:
            return float(given) > float(target) if op == "gt" else float(given) < float(target)
        except (TypeError, ValueError):
            return False
    if op == "in":
        return str(given) in {x.strip() for x in str(target or "").split(",")}
    return (str(given) == str(target)) == (op != "neq")


# ── surveys and their window ────────────────────────────────────────────


def survey(conn, evaluation_id) -> dict:
    ensure(conn)
    row = _one(conn, "SELECT * FROM course_evaluations WHERE evaluation_id = ? AND "
                     "course_code IS NOT NULL", (evaluation_id,))
    if not row:
        raise ValueError("No such course survey")
    return row


def state(s, now=None) -> str:
    """scheduled / open / closed (or deleted)."""
    today = _now(now).date().isoformat()
    if s.get("deleted_at"):
        return "deleted"
    if not s.get("is_active"):
        return "closed"
    if str(s.get("start_date") or "")[:10] > today:
        return "scheduled"
    if str(s.get("end_date") or "9999")[:10] < today:
        return "closed"
    return "open"


def default_window(conn, today=None):
    """The last ``WINDOW_DAYS`` of the current (or next) term; three weeks
    from today when no term is recorded."""
    from education_system.systems.university.application.teaching import (
        occurrences as timetable_occurrences,
    )
    today = today or date.today()
    current = sorted((s, e) for _, s, e in timetable_occurrences.terms(conn) if e >= today)
    if not current:
        return today, today + timedelta(days=WINDOW_DAYS)
    end = current[0][1]
    return max(today, end - timedelta(days=WINDOW_DAYS)), end


def _counts(conn, evaluation_id):
    responses = conn.execute("SELECT COUNT(*) FROM evaluation_responses WHERE "
                             "evaluation_id = ?", (evaluation_id,)).fetchone()[0]
    invited = conn.execute("SELECT COUNT(*) FROM course_eval_invitations WHERE "
                           "evaluation_id = ?", (evaluation_id,)).fetchone()[0]
    return responses, invited


def surveys(conn, *, code=None, viewer=None, admin=False, now=None) -> list[dict]:
    """Course surveys the viewer may manage or read (all of them for admins)."""
    ensure(conn)
    out = []
    for s in _dicts(conn.execute("SELECT * FROM course_evaluations WHERE course_code IS NOT "
                                 "NULL AND deleted_at IS NULL ORDER BY academic_year DESC, "
                                 "course_code")):
        if code and s["course_code"] != code:
            continue
        role = access(conn, s["course_code"], viewer, admin)
        if not role:
            continue
        s["state"] = state(s, now)
        s["responses"], s["invited"] = _counts(conn, s["evaluation_id"])
        s["access"] = role
        out.append(s)
    return out


def _parse_window(conn, opens_at, closes_at, today):
    start, end = default_window(conn, today)
    start = date.fromisoformat(str(opens_at)[:10]) if opens_at else start
    end = date.fromisoformat(str(closes_at)[:10]) if closes_at else end
    if end < today:
        raise ValueError("The closing date has already passed")
    if end <= start:
        raise ValueError("The survey must close after it opens")
    return start, end


def _threshold(value):
    try:
        threshold = int(value)
    except (TypeError, ValueError):
        raise ValueError("Minimum responses must be a whole number") from None
    if threshold < MIN_THRESHOLD:
        raise ValueError(f"Results need at least {MIN_THRESHOLD} responses to stay anonymous")
    return threshold


def open_survey(conn, code, *, template_id=None, opens_at=None, closes_at=None,
                min_responses=5, actor=None, admin=False, year=None, now=None,
                semester="", instructor_id=None) -> dict:
    """Create (or reschedule) the course's survey for the academic year and
    invite every active student on the course. The questions are fixed once
    anyone answers."""
    ensure(conn)
    now = _now(now)
    _require_leader(conn, code, actor, admin)
    year = year or module_evaluation.academic_year(now.date())
    start, end = _parse_window(conn, opens_at, closes_at, now.date())
    threshold = _threshold(min_responses)
    template_id = int(template_id or default_template(conn))
    instructor_id = instructor_id or leader(conn, code) or ""
    existing = _one(conn, "SELECT * FROM course_evaluations WHERE course_code = ? AND "
                          "academic_year = ? AND deleted_at IS NULL", (code, year))
    if existing:
        evaluation_id = existing["evaluation_id"]
        values = [start.isoformat(), end.isoformat(), threshold, actor, semester, instructor_id]
        sql = "start_date = ?, end_date = ?, min_responses = ?, opened_by = ?, semester = ?, " \
              "instructor_id = ?, is_active = 1, closed_at = NULL"
        if not _counts(conn, evaluation_id)[0]:
            sql += ", template_id = ?"
            values.append(_freeze(conn, template_id, f"{code} {year} course survey", actor))
        conn.execute(f"UPDATE course_evaluations SET {sql} WHERE evaluation_id = ?",
                     (*values, evaluation_id))
    else:
        frozen = _freeze(conn, template_id, f"{code} {year} course survey", actor)
        evaluation_id = conn.execute(
            "INSERT INTO course_evaluations (module_code, course_code, academic_year, semester, "
            "instructor_id, template_id, start_date, end_date, is_active, is_anonymous, "
            "min_responses, opened_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)",
            (code, code, year, semester, instructor_id, frozen, start.isoformat(),
             end.isoformat(), threshold, actor)).lastrowid
    invited = invite(conn, evaluation_id)
    emails = _announce(conn, evaluation_id, now) if start <= now.date() else []
    return {"evaluation_id": int(evaluation_id), "opens": start.isoformat(),
            "closes": end.isoformat(), "invited": invited, "emails": emails}


def invite(conn, evaluation_id) -> int:
    """Invite every active student on the course (idempotent)."""
    s = survey(conn, evaluation_id)
    for student in students_on(conn, s["course_code"]):
        conn.execute("INSERT OR IGNORE INTO course_eval_invitations (evaluation_id, student_id) "
                     "VALUES (?, ?)", (evaluation_id, student))
    return _counts(conn, evaluation_id)[1]


def close_survey(conn, evaluation_id, actor=None, admin=False, now=None):
    s = survey(conn, evaluation_id)
    _require_leader(conn, s["course_code"], actor, admin)
    now = _now(now)
    conn.execute("UPDATE course_evaluations SET is_active = 0, closed_at = ?, end_date = "
                 "MIN(end_date, ?) WHERE evaluation_id = ?",
                 (now.strftime("%Y-%m-%d %H:%M:%S"), now.date().isoformat(), evaluation_id))
    refresh_instructor_history(conn, s["academic_year"])


# ── students ────────────────────────────────────────────────────────────


def student_surveys(conn, student_id, now=None) -> list[dict]:
    """The student's course surveys with their state (answered when done)."""
    ensure(conn)
    code = course_for_student(conn, student_id)
    if not code:
        return []
    out = []
    for s in _dicts(conn.execute("SELECT * FROM course_evaluations WHERE course_code = ? AND "
                                 "deleted_at IS NULL ORDER BY academic_year DESC", (code,))):
        current = state(s, now)
        if current == "open":
            conn.execute("INSERT OR IGNORE INTO course_eval_invitations (evaluation_id, "
                         "student_id) VALUES (?, ?)", (s["evaluation_id"], str(student_id)))
        inv = conn.execute("SELECT responded FROM course_eval_invitations WHERE "
                           "evaluation_id = ? AND student_id = ?",
                           (s["evaluation_id"], str(student_id))).fetchone()
        s["state"] = "answered" if inv and inv[0] else current
        out.append(s)
    return out


def _check_answer(q, value):
    """``(answer_value, numeric_value)`` for a valid answer."""
    kind = q["question_type"]
    if kind in NUMERIC:
        if not isinstance(value, int) or isinstance(value, bool) or \
                not q["scale_min"] <= value <= q["scale_max"]:
            raise ValueError(f"Ratings run from {q['scale_min']} to {q['scale_max']}")
        return str(value), float(value)
    text = str(value).strip()
    if kind == "text":
        return text, None
    if q["choices"] and text not in q["choices"]:
        raise ValueError(f"Choose one of: {', '.join(q['choices'])}")
    return text, (1.0 if text == "Yes" else 0.0) if kind == "yes/no" else None


def _validated(conn, evaluation_id, answers):
    shown_answers = {k: v for k, v in answers.items() if v not in (None, "")}
    out, missing = [], []
    for q in questions(conn, evaluation_id):
        if not should_show(q, shown_answers):
            continue
        value = shown_answers.get(q["question_id"])
        if value is None:
            if q["is_required"]:
                missing.append(q["question_text"])
            continue
        out.append((q["question_id"], *_check_answer(q, value), q["question_type"]))
    if missing:
        raise ValueError("Please answer: " + "; ".join(missing[:3]))
    return out


def _eligible(conn, s, student_id):
    if course_for_student(conn, student_id) != s["course_code"]:
        raise ValueError("Only students on the course can evaluate it")
    conn.execute("INSERT OR IGNORE INTO course_eval_invitations (evaluation_id, student_id) "
                 "VALUES (?, ?)", (s["evaluation_id"], student_id))
    if conn.execute("SELECT responded FROM course_eval_invitations WHERE evaluation_id = ? AND "
                    "student_id = ?", (s["evaluation_id"], student_id)).fetchone()[0]:
        raise ValueError("You have already evaluated your course this year")


def submit(conn, evaluation_id, student_id, answers: dict, now=None) -> dict:
    """Record a response. ``answers`` is ``{question_id: value}`` - an int
    for ratings, text otherwise."""
    s = survey(conn, evaluation_id)
    if state(s, now) != "open":
        raise ValueError("This survey is not open")
    student_id = str(student_id)
    _eligible(conn, s, student_id)
    rows = _validated(conn, evaluation_id, answers)
    day = _now(now).date().isoformat()
    response_id = conn.execute(
        "INSERT INTO evaluation_responses (evaluation_id, student_id, is_complete, "
        "is_anonymous, submitted_at, response_date) VALUES (?, ?, 1, 1, ?, ?)",
        (evaluation_id, f"tok-{secrets.token_hex(16)}", day, day)).lastrowid
    flagged = 0
    for question_id, value, numeric, kind in rows:
        answer_id = conn.execute("INSERT INTO evaluation_answers (response_id, question_id, "
                                 "answer_value, numeric_value) VALUES (?, ?, ?, ?)",
                                 (response_id, question_id, value, numeric)).lastrowid
        reason = module_evaluation.screen(conn, value) if kind == "text" else None
        if reason:
            conn.execute("INSERT INTO course_eval_comment_reviews (answer_id, reason) "
                         "VALUES (?, ?)", (answer_id, reason))
            flagged += 1
    conn.execute("UPDATE course_eval_invitations SET responded = 1 WHERE evaluation_id = ? AND "
                 "student_id = ?", (evaluation_id, student_id))
    responses, invited = _counts(conn, evaluation_id)
    conn.execute("UPDATE course_evaluations SET response_count = ?, completion_rate = ? WHERE "
                 "evaluation_id = ?", (responses, round(responses / invited * 100, 1)
                                       if invited else 0, evaluation_id))
    return {"flagged": flagged}


# ── results ─────────────────────────────────────────────────────────────


def _question_stats(conn, q):
    rows = conn.execute("SELECT answer_value, numeric_value FROM evaluation_answers WHERE "
                        "question_id = ?", (q["question_id"],)).fetchall()
    if q["question_type"] in NUMERIC:
        values = [int(r[1]) for r in rows if r[1] is not None]
        dist = {i: values.count(i) for i in range(q["scale_min"], q["scale_max"] + 1)}
        mean = round(sum(values) / len(values), 2) if values else None
        return dict(q, n=len(values), mean=mean, distribution=dist)
    values = [r[0] for r in rows if r[0]]
    dist = {c: values.count(c) for c in (q["choices"] or sorted(set(values)))}
    return dict(q, n=len(values), mean=None, distribution=dist)


def _overall_mean(conn, evaluation_id):
    q = next((q for q in questions(conn, evaluation_id) if is_overall(q)), None)
    if not q:
        return None
    row = conn.execute("SELECT AVG(numeric_value) FROM evaluation_answers WHERE question_id = ?",
                       (q["question_id"],)).fetchone()
    return round(row[0], 2) if row and row[0] is not None else None


def _shown(conn, s):
    return _counts(conn, s["evaluation_id"])[0] >= (s.get("min_responses") or 5)


def _comparison(conn, s):
    previous = _one(conn, "SELECT * FROM course_evaluations WHERE course_code = ? AND "
                          "academic_year < ? AND deleted_at IS NULL ORDER BY academic_year DESC "
                          "LIMIT 1", (s["course_code"], s["academic_year"]))
    dept = course(conn, s["course_code"]).get("department")
    peers = [p for p in _dicts(conn.execute(
        "SELECT e.* FROM course_evaluations e JOIN courses c ON COALESCE(NULLIF(c.course_code, "
        "''), c.code) = e.course_code WHERE e.academic_year = ? AND e.evaluation_id <> ? AND "
        "e.deleted_at IS NULL AND c.department = ?",
        (s["academic_year"], s["evaluation_id"], dept))) if _shown(conn, p)]
    means = [m for m in (_overall_mean(conn, p["evaluation_id"]) for p in peers) if m is not None]
    return {"last_year": _overall_mean(conn, previous["evaluation_id"])
            if previous and _shown(conn, previous) else None,
            "department": round(sum(means) / len(means), 2) if means else None,
            "department_courses": len(means)}


def module_rollup(conn, code, academic_year) -> list[dict]:
    """The course's module surveys for the year (overall only where each
    met its own anonymity threshold)."""
    names = _names(conn, code)
    marks = ", ".join("?" for _ in names)
    out = []
    for module_code, name in conn.execute(f"SELECT module_code, module_name FROM modules WHERE "
                                          f"course IN ({marks}) ORDER BY module_code", names):
        for row in module_evaluation.module_summary(conn, module_code):
            if row["academic_year"] == academic_year:
                out.append({"module_code": module_code, "module_name": name, **row})
    return out


def results(conn, evaluation_id, viewer, admin=False) -> dict:
    s = survey(conn, evaluation_id)
    if not access(conn, s["course_code"], viewer, admin):
        raise ValueError("Only the course team and admins can see its results")
    responses, invited = _counts(conn, evaluation_id)
    threshold = s.get("min_responses") or 5
    out = {"survey": s, "state": state(s), "responses": responses, "invited": invited,
           "rate": round(responses / invited * 100, 1) if invited else None,
           "threshold": threshold, "withheld": responses < threshold,
           "modules": module_rollup(conn, s["course_code"], s["academic_year"])}
    if out["withheld"]:
        return dict(out, questions=[], comments=[], comparison={}, overall=None)
    qs = questions(conn, evaluation_id)
    out["questions"] = [_question_stats(conn, q) for q in qs if q["question_type"] != "text"]
    out["comments"] = _comments(conn, [q["question_id"] for q in qs
                                       if q["question_type"] == "text"])
    out["comparison"] = _comparison(conn, s)
    out["overall"] = _overall_mean(conn, evaluation_id)
    return out


def _comments(conn, question_ids):
    if not question_ids:
        return []
    marks = ", ".join("?" for _ in question_ids)
    return [r[0] for r in conn.execute(
        f"SELECT a.answer_value FROM evaluation_answers a LEFT JOIN course_eval_comment_reviews "
        f"v ON v.answer_id = a.answer_id WHERE a.question_id IN ({marks}) AND "
        f"COALESCE(a.answer_value, '') <> '' AND (v.answer_id IS NULL OR "
        f"v.status = 'released') ORDER BY a.answer_id", question_ids)]


def export_csv(result, path) -> int:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["question", "type", "responses", "mean", "distribution"])
        for q in result["questions"]:
            writer.writerow([q["question_text"], q["question_type"], q["n"], q["mean"],
                             "; ".join(f"{k}: {v}" for k, v in q["distribution"].items())])
        for m in result["modules"]:
            writer.writerow([f"Module {m['module_code']} overall", "module survey",
                             m["responses"], m["overall"], ""])
    return len(result["questions"])


# ── comment review ──────────────────────────────────────────────────────


def review_queue(conn) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute(
        "SELECT v.answer_id, v.reason, a.answer_value AS text_value, e.course_code, "
        "e.academic_year FROM course_eval_comment_reviews v JOIN evaluation_answers a ON "
        "a.answer_id = v.answer_id JOIN evaluation_responses r ON r.response_id = a.response_id "
        "JOIN course_evaluations e ON e.evaluation_id = r.evaluation_id WHERE "
        "v.status = 'pending' ORDER BY v.answer_id"))


def review_comment(conn, answer_id, release: bool, actor):
    ensure(conn)
    if not conn.execute("UPDATE course_eval_comment_reviews SET status = ?, reviewed_by = ?, "
                        "reviewed_at = datetime('now') WHERE answer_id = ? AND "
                        "status = 'pending'", ("released" if release else "withheld", actor,
                                               answer_id)).rowcount:
        raise ValueError("That comment is not waiting for review")


# ── reminders and closing the loop ──────────────────────────────────────


def _notify(conn, student_id, subject, body):
    from education_system.systems.university.infrastructure.email.messages_inbox import (
        deliver_inbox_message_on,
    )
    deliver_inbox_message_on(conn, student_id, subject, body)
    row = conn.execute("SELECT email_address FROM students WHERE student_id = ?",
                       (student_id,)).fetchone()
    return [(row[0], subject, body)] if row and row[0] and "@" in row[0] else []


def _announce(conn, evaluation_id, now) -> list:
    s = survey(conn, evaluation_id)
    emails = []
    for (sid,) in conn.execute("SELECT student_id FROM course_eval_invitations WHERE "
                               "evaluation_id = ? AND responded = 0 AND reminded_at IS NULL",
                               (evaluation_id,)).fetchall():
        emails += _notify(conn, sid, f"Tell us about your course ({s['course_code']})",
                          f"The {s['academic_year']} course survey for {s['course_code']} is "
                          f"open until {s['end_date']}. It is anonymous and takes about five "
                          "minutes.")
        conn.execute("UPDATE course_eval_invitations SET reminded_at = ? WHERE evaluation_id = ? "
                     "AND student_id = ?", (now.date().isoformat(), evaluation_id, sid))
    return emails


def send_reminders(conn, now=None) -> dict:
    """Remind invited students who have not answered an open survey, at most
    every ``REMIND_EVERY_DAYS``. Nobody who has answered is contacted."""
    ensure(conn)
    now = _now(now)
    cutoff = (now.date() - timedelta(days=REMIND_EVERY_DAYS)).isoformat()
    emails, sent = [], 0
    for s in _dicts(conn.execute("SELECT * FROM course_evaluations WHERE course_code IS NOT "
                                 "NULL AND is_active = 1 AND deleted_at IS NULL")):
        if state(s, now) != "open":
            continue
        for (sid,) in conn.execute("SELECT student_id FROM course_eval_invitations WHERE "
                                   "evaluation_id = ? AND responded = 0 AND (reminded_at IS "
                                   "NULL OR reminded_at <= ?)",
                                   (s["evaluation_id"], cutoff)).fetchall():
            emails += _notify(conn, sid, f"Reminder: your {s['course_code']} course survey",
                              f"The course survey closes on {s['end_date']}. It is anonymous.")
            conn.execute("UPDATE course_eval_invitations SET reminded_at = ? WHERE "
                         "evaluation_id = ? AND student_id = ?",
                         (now.date().isoformat(), s["evaluation_id"], sid))
            sent += 1
    return {"sent": sent, "emails": emails}


def respond(conn, evaluation_id, summary, actions="", you_said="", we_did="", actor=None,
            admin=False, now=None) -> int:
    s = survey(conn, evaluation_id)
    _require_leader(conn, s["course_code"], actor, admin)
    if not (summary or "").strip():
        raise ValueError("Write a short response to the results")
    if state(s, now) != "closed":
        raise ValueError("Respond once the survey has closed")
    return int(conn.execute("INSERT INTO course_eval_responses_to_students (evaluation_id, "
                            "summary, actions, you_said, we_did, author) VALUES "
                            "(?, ?, ?, ?, ?, ?)", (evaluation_id, summary.strip(),
                                                   actions or None, you_said or None,
                                                   we_did or None, actor)).lastrowid)


def publish(conn, response_id, actor=None, admin=False) -> dict:
    ensure(conn)
    row = _one(conn, "SELECT * FROM course_eval_responses_to_students WHERE id = ?",
               (response_id,))
    if not row:
        raise ValueError("No such response")
    s = survey(conn, row["evaluation_id"])
    _require_leader(conn, s["course_code"], actor, admin)
    if not (row["you_said"] and row["we_did"]):
        raise ValueError("Fill in 'you said' and 'we did' before publishing")
    conn.execute("UPDATE course_eval_responses_to_students SET published = 1, published_at = "
                 "datetime('now') WHERE id = ?", (response_id,))
    emails, notified = [], 0
    for (sid,) in conn.execute("SELECT student_id FROM course_eval_invitations WHERE "
                               "evaluation_id = ?", (row["evaluation_id"],)).fetchall():
        emails += _notify(conn, sid, f"{s['course_code']}: you said, we did",
                          f"You said: {row['you_said']}\n\nWe did: {row['we_did']}\n\n"
                          f"{row['summary']}")
        notified += 1
    return {"notified": notified, "emails": emails}


def loop_records(conn, evaluation_id) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute("SELECT * FROM course_eval_responses_to_students WHERE "
                               "evaluation_id = ? ORDER BY id", (evaluation_id,)))


def published_for_student(conn, student_id) -> list[dict]:
    ensure(conn)
    code = course_for_student(conn, student_id)
    if not code:
        return []
    return _dicts(conn.execute(
        "SELECT e.course_code, e.academic_year, r.summary, r.actions, r.you_said, r.we_did, "
        "r.published_at FROM course_eval_responses_to_students r JOIN course_evaluations e ON "
        "e.evaluation_id = r.evaluation_id WHERE r.published = 1 AND e.course_code = ? "
        "ORDER BY r.published_at DESC", (code,)))
