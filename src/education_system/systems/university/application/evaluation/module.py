"""Module evaluation surveys.

The portal used to create a module's survey the first time any student
opened it, leave it open for ever, ask the same eight questions everywhere,
tag responses with a reversible hash of the student id and show results — to
admins only — as a text dump regardless of how few people had answered.

Here a survey is *opened* for a module and academic year by its leader or an
admin:

* **Window** — it runs between ``opens_at`` and ``closes_at`` (by default
  the last three weeks of the term the module is taught in), and closes early
  as soon as any of the module's marks are released.
* **Questions** — the standard set, every question in the bank tagged
  ``required`` (institution-wide), any bank or custom questions the leader
  adds, and two questions about each member of the teaching team.
* **Invitations** — every student enrolled on the module is invited; that is
  the response-rate denominator and who gets reminders. Whether a student has
  answered lives only on their invitation, never on the response.
* **Results** — shown only once ``min_responses`` (default 5) have answered;
  leaders and admins see everything, other team members see the module
  questions and their own. Free-text comments that match a screening rule are
  held for review before anyone sees them.
* **Closing the loop** — the leader writes a response and actions; publishing
  it sends "you said, we did" to the invited students.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import csv
import re
import secrets
from datetime import date, datetime, timedelta

from education_system.systems.university.infrastructure.database.schemas import (
    module_evaluation_schema as schema,
)

LIKERT = ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"]
STANDARD = [
    "The module learning objectives were clearly explained.",
    "The content was well-structured and organised.",
    "Assessment methods were fair and appropriate.",
    "Feedback on assignments was timely and helpful.",
    "The workload was reasonable for the credits awarded.",
    "Learning resources (materials, readings) were useful.",
    "I would recommend this module to other students.",
]
OVERALL = "Overall Module Rating (1 = Poor, 5 = Excellent)"
COMMENTS = "Additional Comments"
STAFF_QUESTIONS = ["{name} explained things clearly.", "{name} was approachable and helpful."]
WINDOW_DAYS = 21
REMIND_EVERY_DAYS = 3
SCREEN = (
    ("abusive language", r"\b(idiot|stupid|moron|useless|pathetic|hate (him|her|them)|"
                         r"f+u+c+k\w*|sh[i1]t\w*|bitch\w*|bastard\w*|wank\w*|cunt\w*|"
                         r"retard\w*|kill)\b"),
    ("remarks about appearance or identity", r"\b(ugly|fat|old|racist|sexist|gay|accent)\b"),
    ("contact details", r"[\w.+-]+@[\w-]+\.\w+|\b\d{5}\s?\d{6}\b"),
)


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


def academic_year(today=None):
    today = today or date.today()
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start}/{start + 1}"


# ── forms and their window ──────────────────────────────────────────────


def form(conn, form_id) -> dict:
    ensure(conn)
    row = _one(conn, "SELECT * FROM evaluation_forms WHERE id = ?", (form_id,))
    if not row:
        raise ValueError("No such survey")
    return row


def marks_released(conn, module_code, since) -> bool:
    """Any of the module's marks released since the survey opened."""
    for sql in ("SELECT 1 FROM assignments WHERE module_code = ? AND grades_released_at >= ?",
                "SELECT 1 FROM assessments WHERE module_code = ? AND marks_released_at >= ?"):
        try:
            if conn.execute(sql, (module_code, since)).fetchone():
                return True
        except Exception:
            continue
    return False


def state(conn, f, now=None) -> str:
    """scheduled / open / closed (``closed_marks`` when marks were released)."""
    now = _now(now)
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    if f["status"] in ("closed", "draft"):
        return "closed" if f["status"] == "closed" else "scheduled"
    if f.get("opens_at") and f["opens_at"] > stamp:
        return "scheduled"
    if f.get("closes_at") and f["closes_at"] < stamp:
        return "closed"
    if marks_released(conn, f["module_code"], f.get("opens_at") or f["created_at"] or stamp):
        return "closed_marks"
    return "open"


def default_window(conn, module_code, today=None):
    """The last ``WINDOW_DAYS`` of the term the module is taught in (its
    delivery's term, else the term named by its semester, else the current
    term). Falls back to three weeks from today."""
    from education_system.systems.university.application.teaching import (
        occurrences as timetable_occurrences,
    )
    today = today or date.today()
    terms = timetable_occurrences.terms(conn)
    chosen = None
    section = _one(conn, "SELECT t.name, t.start_date, t.end_date FROM course_sections s JOIN "
                         "academic_terms t ON t.id = s.term_id WHERE s.course_code = ? AND "
                         "t.end_date >= ? ORDER BY t.start_date LIMIT 1",
                   (module_code, today.isoformat())) if _has(conn, "course_sections") else None
    if section:
        chosen = (date.fromisoformat(section["start_date"][:10]),
                  date.fromisoformat(section["end_date"][:10]))
    else:
        semester = (_one(conn, "SELECT semester FROM modules WHERE module_code = ?",
                         (module_code,)) or {}).get("semester") or ""
        matching = [(s, e) for name, s, e in terms if e >= today and
                    (not semester or semester.lower() in str(name).lower())]
        chosen = min(matching) if matching else None
    if not chosen:
        return today, today + timedelta(days=WINDOW_DAYS)
    return max(today, chosen[1] - timedelta(days=WINDOW_DAYS)), chosen[1]


def _has(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (table,)).fetchone()


# ── opening a survey ────────────────────────────────────────────────────


def is_leader(conn, module_code, username) -> bool:
    from education_system.systems.university.application.modules import delivery as module_delivery
    return module_delivery.is_leader(conn, module_code, username)


def team(conn, module_code) -> list[dict]:
    """``[{username, name}]`` of everyone teaching the module."""
    from education_system.systems.university.application.modules import delivery as module_delivery
    people = {m["username"]: m["name"] or m["username"]
              for m in module_delivery.team(conn, module_code)}
    leader = module_delivery.leader(conn, module_code)
    if leader and leader not in people:
        row = conn.execute("SELECT TRIM(first_name || ' ' || last_name) FROM users WHERE "
                           "username = ?", (leader,)).fetchone()
        people[leader] = (row[0] if row and row[0].strip() else leader)
    return [{"username": u, "name": n} for u, n in sorted(people.items())]


def required_bank(conn) -> list[dict]:
    try:
        return _dicts(conn.execute(
            "SELECT b.bank_id, b.question_text, b.question_type FROM evaluation_question_bank b "
            "JOIN evaluation_question_tags t ON t.bank_id = b.bank_id WHERE t.tag = 'required' "
            "ORDER BY b.bank_id"))
    except Exception:
        return []


def bank(conn) -> list[dict]:
    try:
        rows = _dicts(conn.execute("SELECT bank_id, question_text, question_type, "
                                   "question_category FROM evaluation_question_bank "
                                   "ORDER BY question_category, question_text"))
    except Exception:
        return []
    required = {r["bank_id"] for r in required_bank(conn)}
    return [dict(r, required=r["bank_id"] in required) for r in rows]


def set_required(conn, bank_id, required: bool):
    ensure(conn)
    conn.execute("DELETE FROM evaluation_question_tags WHERE bank_id = ? AND tag = 'required'",
                 (bank_id,))
    if required:
        conn.execute("INSERT INTO evaluation_question_tags (bank_id, tag) VALUES (?, 'required')",
                     (bank_id,))


def _question_rows(conn, module_code, bank_ids, custom, include_staff):
    rows = [(q, "likert", "standard", "module", None) for q in STANDARD]
    picked = {r["bank_id"]: r for r in bank(conn)}
    required = required_bank(conn)
    required_ids = {r["bank_id"] for r in required}
    chosen = required + [picked[i] for i in bank_ids if i in picked and i not in required_ids]
    for b in chosen:
        kind = "text" if b["question_type"] == "text" else "likert"
        source = "institution" if b["bank_id"] in required_ids else "bank"
        if not any(r[0] == b["question_text"] for r in rows):
            rows.append((b["question_text"], kind, source, "module", None))
    rows += [(text.strip(), kind, "module", "module", None) for text, kind in custom
             if text.strip()]
    if include_staff:
        for person in team(conn, module_code):
            rows += [(q.format(name=person["name"]), "likert", "staff", "staff",
                      person["username"]) for q in STAFF_QUESTIONS]
    rows += [(OVERALL, "rating", "standard", "module", None),
             (COMMENTS, "text", "standard", "module", None)]
    return rows


def open_survey(conn, module_code, *, opens_at=None, closes_at=None, bank_ids=(),
                custom=(), include_staff=False, min_responses=5, actor=None,
                year=None, now=None) -> dict:
    """Create (or reschedule) the module's survey for the academic year and
    invite every enrolled student. Questions are fixed once anyone answers."""
    ensure(conn)
    now = _now(now)
    year = year or academic_year(now.date())
    module = _one(conn, "SELECT module_code, module_name FROM modules WHERE module_code = ?",
                  (module_code,))
    if not module:
        raise ValueError(f"No module {module_code}")
    start, end = default_window(conn, module_code, now.date())
    start = date.fromisoformat(str(opens_at)[:10]) if opens_at else start
    end = date.fromisoformat(str(closes_at)[:10]) if closes_at else end
    if end <= start:
        raise ValueError("The survey must close after it opens")
    try:
        threshold = int(min_responses)
    except (TypeError, ValueError):
        raise ValueError("Minimum responses must be a whole number") from None
    if threshold < 3:
        raise ValueError("Results need at least 3 responses to stay anonymous")
    existing = _one(conn, "SELECT * FROM evaluation_forms WHERE module_code = ? AND "
                          "academic_year = ?", (module_code, year))
    window = (f"{start.isoformat()} 00:00:00", f"{end.isoformat()} 23:59:59")
    if existing:
        answered = conn.execute("SELECT COUNT(*) FROM eval_form_responses WHERE form_id = ?",
                                (existing["id"],)).fetchone()[0]
        conn.execute("UPDATE evaluation_forms SET opens_at = ?, closes_at = ?, status = 'open', "
                     "min_responses = ?, opened_by = ? WHERE id = ?",
                     (*window, threshold, actor, existing["id"]))
        form_id = existing["id"]
        if not answered:
            conn.execute("DELETE FROM eval_form_questions WHERE form_id = ?", (form_id,))
            _add_questions(conn, form_id, module_code, bank_ids, custom, include_staff)
    else:
        form_id = conn.execute(
            "INSERT INTO evaluation_forms (module_code, module_name, academic_year, semester, "
            "status, created_by, created_at, closes_at, is_anonymous, opens_at, min_responses, "
            "opened_by) VALUES (?, ?, ?, '', 'open', ?, ?, ?, 1, ?, ?, ?)",
            (module_code, module["module_name"] or module_code, year, actor,
             now.strftime("%Y-%m-%d %H:%M:%S"), window[1], window[0], threshold, actor)).lastrowid
        _add_questions(conn, form_id, module_code, bank_ids, custom, include_staff)
    invited = invite(conn, form_id)
    return {"form_id": int(form_id), "opens": start.isoformat(), "closes": end.isoformat(),
            "invited": invited, "emails": _announce(conn, form_id, now) if start <= now.date()
            else []}


def _add_questions(conn, form_id, module_code, bank_ids, custom, include_staff):
    import json
    for order, (text, kind, source, scope, staff) in enumerate(
            _question_rows(conn, module_code, list(bank_ids), list(custom), include_staff), 1):
        options = json.dumps(LIKERT) if kind == "likert" else (
            json.dumps([1, 2, 3, 4, 5]) if kind == "rating" else None)
        conn.execute("INSERT INTO eval_form_questions (form_id, question_text, question_type, "
                     "options, display_order, is_required, scope, staff_username, source) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (form_id, text, kind, options, order, 0 if kind == "text" else 1, scope,
                      staff, source))


def invite(conn, form_id) -> int:
    """Invite every student currently enrolled on the module (idempotent)."""
    f = form(conn, form_id)
    conn.execute("INSERT OR IGNORE INTO eval_form_invitations (form_id, student_id) "
                 "SELECT ?, student_id FROM student_modules WHERE module_code = ? AND "
                 "LOWER(COALESCE(status, '')) = 'enrolled'", (form_id, f["module_code"]))
    return conn.execute("SELECT COUNT(*) FROM eval_form_invitations WHERE form_id = ?",
                        (form_id,)).fetchone()[0]


def close_survey(conn, form_id):
    form(conn, form_id)
    conn.execute("UPDATE evaluation_forms SET status = 'closed', closes_at = ? WHERE id = ?",
                 (_now().strftime("%Y-%m-%d %H:%M:%S"), form_id))


def forms_for(conn, *, module_code=None, staff=None, admin=False) -> list[dict]:
    """Surveys a member of staff may manage or read."""
    ensure(conn)
    rows = _dicts(conn.execute("SELECT * FROM evaluation_forms ORDER BY academic_year DESC, "
                               "module_code"))
    out = []
    for f in rows:
        if module_code and f["module_code"] != module_code:
            continue
        people = {p["username"] for p in team(conn, f["module_code"])}
        if admin or (staff and staff in people):
            f["state"] = state(conn, f)
            f["responses"] = conn.execute("SELECT COUNT(*) FROM eval_form_responses WHERE "
                                          "form_id = ?", (f["id"],)).fetchone()[0]
            f["invited"] = conn.execute("SELECT COUNT(*) FROM eval_form_invitations WHERE "
                                        "form_id = ?", (f["id"],)).fetchone()[0]
            f["leads"] = admin or is_leader(conn, f["module_code"], staff)
            out.append(f)
    return out


# ── students ────────────────────────────────────────────────────────────


def student_surveys(conn, student_id, now=None) -> list[dict]:
    """The student's module surveys: open (to answer), answered, scheduled or closed."""
    ensure(conn)
    out = []
    for f in _dicts(conn.execute(
            "SELECT f.* FROM evaluation_forms f JOIN student_modules sm ON sm.module_code = "
            "f.module_code WHERE sm.student_id = ? AND LOWER(COALESCE(sm.status, '')) = "
            "'enrolled' ORDER BY f.academic_year DESC, f.module_code", (str(student_id),))):
        current = state(conn, f, now)
        if current == "open":
            conn.execute("INSERT OR IGNORE INTO eval_form_invitations (form_id, student_id) "
                         "VALUES (?, ?)", (f["id"], str(student_id)))
        inv = _one(conn, "SELECT responded FROM eval_form_invitations WHERE form_id = ? AND "
                         "student_id = ?", (f["id"], str(student_id)))
        f["state"] = "answered" if inv and inv["responded"] else current
        out.append(f)
    return out


def questions(conn, form_id) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute("SELECT id, question_text, question_type, options, is_required, "
                               "COALESCE(scope, 'module') AS scope, staff_username, "
                               "COALESCE(source, 'standard') AS source FROM eval_form_questions "
                               "WHERE form_id = ? ORDER BY display_order, id", (form_id,)))


def screen(conn, text) -> str | None:
    """Why a comment needs reviewing before staff see it, or None."""
    if not (text or "").strip():
        return None
    rules = list(SCREEN)
    try:
        rules += [(r[0], r[1]) for r in conn.execute(
            "SELECT category, pattern FROM evaluation_red_flag_rules")]
    except Exception:
        pass
    for reason, pattern in rules:
        try:
            if re.search(pattern, text, re.IGNORECASE):
                return reason
        except re.error:
            continue
    return None


def submit(conn, form_id, student_id, answers: dict, now=None) -> dict:
    """Record a response. ``answers`` is ``{question_id: (rating, text)}``."""
    f = form(conn, form_id)
    if state(conn, f, now) != "open":
        raise ValueError("This survey is not open")
    student_id = str(student_id)
    if not conn.execute("SELECT 1 FROM student_modules WHERE student_id = ? AND module_code = ? "
                        "AND LOWER(COALESCE(status, '')) = 'enrolled'",
                        (student_id, f["module_code"])).fetchone():
        raise ValueError("Only students on the module can evaluate it")
    conn.execute("INSERT OR IGNORE INTO eval_form_invitations (form_id, student_id) VALUES (?, ?)",
                 (form_id, student_id))
    if conn.execute("SELECT responded FROM eval_form_invitations WHERE form_id = ? AND "
                    "student_id = ?", (form_id, student_id)).fetchone()[0]:
        raise ValueError("You have already evaluated this module this year")
    qs = {q["id"]: q for q in questions(conn, form_id)}
    for qid, (rating, _text) in answers.items():
        if rating is not None and qid in qs and not (
                isinstance(rating, int) and 1 <= rating <= 5):
            raise ValueError("Ratings run from 1 to 5")
    missing = [q["question_text"] for qid, q in qs.items() if q["is_required"]
               and (answers.get(qid) or (None, None))[0] is None]
    if missing:
        raise ValueError("Please answer: " + "; ".join(missing[:3]))
    response_id = conn.execute("INSERT INTO eval_form_responses (form_id, student_hash, "
                               "submitted_at) VALUES (?, ?, ?)",
                               (form_id, f"tok-{secrets.token_hex(16)}",
                                _now(now).date().isoformat())).lastrowid
    flagged = 0
    for qid, (rating, text) in answers.items():
        if qid not in qs:
            continue
        answer_id = conn.execute("INSERT INTO eval_form_answers (response_id, question_id, "
                                 "rating_value, text_value) VALUES (?, ?, ?, ?)",
                                 (response_id, qid, rating, (text or "").strip() or None)
                                 ).lastrowid
        reason = screen(conn, text)
        if reason:
            conn.execute("INSERT INTO eval_form_comment_reviews (answer_id, reason) VALUES (?, ?)",
                         (answer_id, reason))
            flagged += 1
    conn.execute("UPDATE eval_form_invitations SET responded = 1 WHERE form_id = ? AND "
                 "student_id = ?", (form_id, student_id))
    return {"flagged": flagged}


# ── results ─────────────────────────────────────────────────────────────


def _visible(conn, f, viewer, admin):
    if admin or is_leader(conn, f["module_code"], viewer):
        return "all"
    if viewer in {p["username"] for p in team(conn, f["module_code"])}:
        return "own"
    raise ValueError("Only the module's teaching team and admins can see its results")


def _mean_of(conn, form_ids, text):
    if not form_ids:
        return None
    marks = ", ".join("?" for _ in form_ids)
    return conn.execute(f"SELECT AVG(a.rating_value) FROM eval_form_answers a JOIN "
                        f"eval_form_questions q ON q.id = a.question_id WHERE q.form_id IN "
                        f"({marks}) AND q.question_text = ?", (*form_ids, text)).fetchone()[0]


def _comparison(conn, f):
    previous = [r[0] for r in conn.execute("SELECT id FROM evaluation_forms WHERE module_code = ? "
                                           "AND academic_year < ? ORDER BY academic_year DESC "
                                           "LIMIT 1", (f["module_code"], f["academic_year"]))]
    dept = conn.execute("SELECT COALESCE(NULLIF(department, ''), course) FROM modules WHERE "
                        "module_code = ?", (f["module_code"],)).fetchone()
    peers = [r[0] for r in conn.execute(
        "SELECT f.id FROM evaluation_forms f JOIN modules m ON m.module_code = f.module_code "
        "WHERE f.academic_year = ? AND COALESCE(NULLIF(m.department, ''), m.course) = ? "
        "AND f.id <> ? AND (SELECT COUNT(*) FROM eval_form_responses r WHERE r.form_id = f.id) "
        ">= COALESCE(f.min_responses, 5)", (f["academic_year"], dept[0] if dept else None,
                                           f["id"]))]
    return {"last_year": _mean_of(conn, previous, OVERALL),
            "department": _mean_of(conn, peers, OVERALL), "department_modules": len(peers)}


def _question_stats(conn, q):
    rows = conn.execute("SELECT rating_value FROM eval_form_answers WHERE question_id = ? AND "
                        "rating_value IS NOT NULL", (q["id"],)).fetchall()
    values = [r[0] for r in rows]
    dist = {i: values.count(i) for i in range(1, 6)}
    return dict(q, n=len(values), mean=round(sum(values) / len(values), 2) if values else None,
                distribution=dist)


def results(conn, form_id, viewer, admin=False) -> dict:
    f = form(conn, form_id)
    scope = _visible(conn, f, viewer, admin)
    responses = conn.execute("SELECT COUNT(*) FROM eval_form_responses WHERE form_id = ?",
                             (form_id,)).fetchone()[0]
    invited = conn.execute("SELECT COUNT(*) FROM eval_form_invitations WHERE form_id = ?",
                           (form_id,)).fetchone()[0]
    threshold = f.get("min_responses") or 5
    out = {"form": f, "state": state(conn, f), "responses": responses, "invited": invited,
           "rate": round(responses / invited * 100, 1) if invited else None,
           "threshold": threshold, "withheld": responses < threshold}
    if out["withheld"]:
        return dict(out, questions=[], comments=[], comparison={})
    qs = [q for q in questions(conn, form_id) if q["scope"] == "module" or scope == "all"
          or q["staff_username"] == viewer]
    out["questions"] = [_question_stats(conn, q) for q in qs if q["question_type"] != "text"]
    text_ids = [q["id"] for q in qs if q["question_type"] == "text"]
    out["comments"] = _comments(conn, text_ids)
    out["comparison"] = _comparison(conn, f)
    out["overall"] = next((q["mean"] for q in out["questions"]
                           if q["question_text"] == OVERALL), None)
    return out


def _comments(conn, question_ids):
    if not question_ids:
        return []
    marks = ", ".join("?" for _ in question_ids)
    return [r[0] for r in conn.execute(
        f"SELECT a.text_value FROM eval_form_answers a LEFT JOIN eval_form_comment_reviews v "
        f"ON v.answer_id = a.id WHERE a.question_id IN ({marks}) AND a.text_value IS NOT NULL "
        f"AND (v.answer_id IS NULL OR v.status = 'released') ORDER BY a.id", question_ids)]


def export_csv(result, path) -> int:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["question", "scope", "responses", "mean", "1", "2", "3", "4", "5"])
        for q in result["questions"]:
            writer.writerow([q["question_text"], q["scope"], q["n"], q["mean"],
                             *[q["distribution"][i] for i in range(1, 6)]])
    return len(result["questions"])


# ── comment review ──────────────────────────────────────────────────────


def review_queue(conn) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute(
        "SELECT v.answer_id, v.reason, a.text_value, f.module_code, f.academic_year FROM "
        "eval_form_comment_reviews v JOIN eval_form_answers a ON a.id = v.answer_id JOIN "
        "eval_form_questions q ON q.id = a.question_id JOIN evaluation_forms f ON f.id = "
        "q.form_id WHERE v.status = 'pending' ORDER BY v.answer_id"))


def review_comment(conn, answer_id, release: bool, actor):
    if not conn.execute("UPDATE eval_form_comment_reviews SET status = ?, reviewed_by = ?, "
                        "reviewed_at = datetime('now') WHERE answer_id = ? AND status = 'pending'",
                        ("released" if release else "withheld", actor, answer_id)).rowcount:
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


def _announce(conn, form_id, now) -> list:
    f = form(conn, form_id)
    emails = []
    for (sid,) in conn.execute("SELECT student_id FROM eval_form_invitations WHERE form_id = ? "
                               "AND responded = 0 AND reminded_at IS NULL", (form_id,)).fetchall():
        emails += _notify(conn, sid, f"Tell us about {f['module_code']}",
                          f"The module evaluation for {f['module_code']} {f['module_name']} is "
                          f"open until {str(f['closes_at'])[:10]}. It is anonymous and takes "
                          "about five minutes.")
        conn.execute("UPDATE eval_form_invitations SET reminded_at = ? WHERE form_id = ? AND "
                     "student_id = ?", (now.date().isoformat(), form_id, sid))
    return emails


def send_reminders(conn, now=None) -> dict:
    """Remind invited students who have not answered an open survey (at most
    every ``REMIND_EVERY_DAYS``). Nobody who has answered is contacted."""
    ensure(conn)
    now = _now(now)
    cutoff = (now.date() - timedelta(days=REMIND_EVERY_DAYS)).isoformat()
    emails, sent = [], 0
    for f in _dicts(conn.execute("SELECT * FROM evaluation_forms WHERE status = 'open'")):
        if state(conn, f, now) != "open":
            continue
        for (sid,) in conn.execute("SELECT student_id FROM eval_form_invitations WHERE "
                                   "form_id = ? AND responded = 0 AND (reminded_at IS NULL OR "
                                   "reminded_at <= ?)", (f["id"], cutoff)).fetchall():
            emails += _notify(conn, sid, f"Reminder: evaluate {f['module_code']}",
                              f"The {f['module_code']} module evaluation closes on "
                              f"{str(f['closes_at'])[:10]}. It is anonymous.")
            conn.execute("UPDATE eval_form_invitations SET reminded_at = ? WHERE form_id = ? AND "
                         "student_id = ?", (now.date().isoformat(), f["id"], sid))
            sent += 1
    return {"sent": sent, "emails": emails}


def respond(conn, form_id, summary, actions="", you_said="", we_did="", actor=None) -> int:
    f = form(conn, form_id)
    if not (summary or "").strip():
        raise ValueError("Write a short response to the results")
    if state(conn, f) == "open":
        raise ValueError("Respond once the survey has closed")
    return int(conn.execute("INSERT INTO eval_form_responses_to_students (form_id, summary, "
                            "actions, you_said, we_did, author) VALUES (?, ?, ?, ?, ?, ?)",
                            (form_id, summary.strip(), actions or None, you_said or None,
                             we_did or None, actor)).lastrowid)


def publish(conn, response_id, actor=None, now=None) -> dict:
    row = _one(conn, "SELECT * FROM eval_form_responses_to_students WHERE id = ?", (response_id,))
    if not row:
        raise ValueError("No such response")
    if not (row["you_said"] and row["we_did"]):
        raise ValueError("Fill in 'you said' and 'we did' before publishing")
    f = form(conn, row["form_id"])
    conn.execute("UPDATE eval_form_responses_to_students SET published = 1, published_at = "
                 "datetime('now') WHERE id = ?", (response_id,))
    emails = []
    for (sid,) in conn.execute("SELECT student_id FROM eval_form_invitations WHERE form_id = ?",
                               (row["form_id"],)).fetchall():
        emails += _notify(conn, sid, f"{f['module_code']}: you said, we did",
                          f"You said: {row['you_said']}\n\nWe did: {row['we_did']}\n\n"
                          f"{row['summary']}")
    return {"notified": len(emails), "emails": emails}


def loop_records(conn, form_id) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute("SELECT * FROM eval_form_responses_to_students WHERE form_id = ? "
                               "ORDER BY id", (form_id,)))


def published_for_student(conn, student_id) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute(
        "SELECT f.module_code, f.academic_year, r.you_said, r.we_did, r.summary, r.published_at "
        "FROM eval_form_responses_to_students r JOIN evaluation_forms f ON f.id = r.form_id "
        "WHERE r.published = 1 AND f.module_code IN (SELECT module_code FROM student_modules "
        "WHERE student_id = ?) ORDER BY r.published_at DESC", (str(student_id),)))


def module_summary(conn, module_code) -> list[dict]:
    """Per academic year for the module record: responses, invited and the
    overall mean (only when the anonymity threshold is met)."""
    ensure(conn)
    out = []
    for f in _dicts(conn.execute("SELECT * FROM evaluation_forms WHERE module_code = ? "
                                 "ORDER BY academic_year DESC", (module_code,))):
        n = conn.execute("SELECT COUNT(*) FROM eval_form_responses WHERE form_id = ?",
                         (f["id"],)).fetchone()[0]
        invited = conn.execute("SELECT COUNT(*) FROM eval_form_invitations WHERE form_id = ?",
                               (f["id"],)).fetchone()[0]
        shown = n >= (f.get("min_responses") or 5)
        out.append({"academic_year": f["academic_year"], "responses": n, "invited": invited,
                    "overall": round(_mean_of(conn, [f["id"]], OVERALL) or 0, 2) if shown and n
                    else None, "withheld": not shown, "state": state(conn, f),
                    "you_said_we_did": [r for r in loop_records(conn, f["id"]) if r["published"]]})
    return out
