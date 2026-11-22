"""Lecturer evaluation: students rate each lecturer who teaches them on a
module. One rule set behind the Lecturer Evaluation window, its CLI menu and
the teaching history.

* **When:** in the module survey's window (``evaluation_forms`` for the
  module and academic year), so a module is surveyed once a year and its
  lecturers alongside it. Opening the module survey is what opens this.
* **Who is rated:** the module's teaching team and leader
  (``module_delivery``), plus timetabled instructors linked to a staff
  record (``instructors.staff_id`` → ``staff.username``).
* **Who answers:** students enrolled on the module, once per lecturer.
  Who answered is kept only on the invitation; the evaluation carries a
  random token and the day.
* **Who reads results:** the lecturer, their line manager
  (``staff_profiles.manager_id``), the module's leader (for that module) and
  admins - and only once ``min_responses`` students have rated the lecturer
  on that module. Comments that look abusive or identifying wait for review.
* **Closing the loop:** after the window the lecturer writes a reflection
  (seen by the same people) and may publish "you said, we did" to the
  module's students.

Results, trends and comparisons are in ``lecturer_feedback``. Functions take
an open connection and do not commit; returned ``emails`` are
``(address, subject, body)`` for the caller to send after committing.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from education_system.systems.university.application.evaluation import module as module_evaluation
from education_system.systems.university.infrastructure.database.schemas import (
    lecturer_evaluation_schema as schema,
)

CRITERIA = (
    ("knowledge", "Subject knowledge", "Knows the subject and explains it accurately"),
    ("communication", "Communication", "Explains clearly and is easy to follow"),
    ("preparation", "Preparation", "Sessions are organised and materials ready"),
    ("engagement", "Engagement", "Makes sessions interesting and involves students"),
    ("fairness", "Fairness", "Treats students fairly and with respect"),
    ("availability", "Availability for help", "Can be reached for questions and support"),
    ("overall", "Overall", "Overall, this lecturer taught me well"),
)
KEYS = tuple(k for k, _l, _d in CRITERIA)
REMIND_EVERY_DAYS = 3
ADMIN_ROLES = ("admin", "administrator", "superadmin")


def ensure(conn):
    module_evaluation.ensure(conn)
    schema.apply_to_connection(conn)


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _one(conn, sql, params=()):
    rows = _dicts(conn.execute(sql, params))
    return rows[0] if rows else None


def _now(now=None):
    return now or datetime.now()


def _has(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (table,)).fetchone()


# ── lecturers and who may see their feedback ────────────────────────────


def name_of(conn, username) -> str:
    row = conn.execute("SELECT TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) "
                       "FROM users WHERE username = ?", (username,)).fetchone()
    if not (row and row[0]) and _has(conn, "staff"):
        row = conn.execute("SELECT name FROM staff WHERE username = ?", (username,)).fetchone()
    return row[0] if row and row[0] else username


def lecturers_for(conn, module_code) -> list[dict]:
    """``[{username, name}]`` teaching the module."""
    people = {p["username"]: p["name"] for p in module_evaluation.team(conn, module_code)}
    if _has(conn, "module_schedule") and _has(conn, "staff") and "staff_id" in {
            r[1] for r in conn.execute("PRAGMA table_info(instructors)")}:
        for (username,) in conn.execute(
                "SELECT DISTINCT s.username FROM module_schedule ms JOIN instructors i ON "
                "i.id = ms.instructor_id JOIN staff s ON s.id = i.staff_id WHERE "
                "ms.module_code = ? AND COALESCE(s.username, '') <> '' AND "
                "COALESCE(i.is_active, 1) = 1", (module_code,)).fetchall():
            people.setdefault(username, name_of(conn, username))
    return [{"username": u, "name": n} for u, n in sorted(people.items())]


def line_manager(conn, username):
    """The lecturer's line manager's username (``staff_profiles.manager_id``
    holds a username or an employee id), or None."""
    if not _has(conn, "staff_profiles"):
        return None
    row = conn.execute("SELECT manager_id FROM staff_profiles WHERE user_id = ?",
                       (username,)).fetchone()
    if not row or not row[0]:
        return None
    by_employee = conn.execute("SELECT user_id FROM staff_profiles WHERE employee_id = ?",
                               (row[0],)).fetchone()
    return by_employee[0] if by_employee else row[0]


def access(conn, lecturer, viewer, admin=False, module_code=None):
    """'admin' / 'self' / 'manager' / 'module leader', or None."""
    if admin:
        return "admin"
    if viewer and viewer == lecturer:
        return "self"
    if viewer and viewer == line_manager(conn, lecturer):
        return "manager"
    if module_code and module_evaluation.is_leader(conn, module_code, viewer):
        return "module leader"
    return None


def visible_lecturers(conn, viewer, admin=False) -> list[dict]:
    """Lecturers whose feedback the viewer may read, with why."""
    ensure(conn)
    names = {}
    for (lecturer,) in conn.execute("SELECT DISTINCT lecturer FROM lecturer_eval_invitations"):
        names[lecturer] = None
    names.setdefault(viewer, None)
    out = []
    for lecturer in sorted(n for n in names if n):
        why = access(conn, lecturer, viewer, admin) or _leads_any(conn, lecturer, viewer)
        if why:
            out.append({"username": lecturer, "name": name_of(conn, lecturer), "access": why})
    return out


def _leads_any(conn, lecturer, viewer):
    for (code,) in conn.execute("SELECT DISTINCT f.module_code FROM lecturer_eval_invitations i "
                                "JOIN evaluation_forms f ON f.id = i.form_id WHERE "
                                "i.lecturer = ?", (lecturer,)).fetchall():
        if module_evaluation.is_leader(conn, code, viewer):
            return "module leader"
    return None


def instructors(conn) -> list[dict]:
    ensure(conn)
    staff = _has(conn, "staff")
    login = "s.username" if staff else "NULL"
    join = "LEFT JOIN staff s ON s.id = i.staff_id " if staff else ""
    # db-audit: ignore[DBW001] - literal clauses only
    return _dicts(conn.execute(
        f"SELECT i.id, TRIM(COALESCE(i.first_name, '') || ' ' || COALESCE(i.last_name, '')) "
        f"AS name, i.email, i.department, {login} AS username FROM instructors i {join}"
        f"WHERE COALESCE(i.is_active, 1) = 1 ORDER BY name"))


def link_instructor(conn, instructor_id, username, admin=False):
    """Admins link a timetabled instructor to a staff record by its
    username (blank unlinks). Same link as ``services/staff_provisioning``."""
    ensure(conn)
    if not admin:
        raise ValueError("Only an admin links instructors to staff")
    username = (username or "").strip()
    staff_id = None
    if username:
        row = conn.execute("SELECT id FROM staff WHERE username = ?", (username,)).fetchone() \
            if _has(conn, "staff") else None
        if not row:
            raise ValueError(f"No staff record has the username {username}")
        staff_id = row[0]
    if not conn.execute("UPDATE instructors SET staff_id = ? WHERE id = ?",
                        (staff_id, instructor_id)).rowcount:
        raise ValueError("No such instructor")


# ── invitations and students ────────────────────────────────────────────


def _enrolled(conn, module_code):
    return [r[0] for r in conn.execute(
        "SELECT student_id FROM student_modules WHERE module_code = ? AND "
        "LOWER(COALESCE(status, '')) = 'enrolled'", (module_code,))]


def sync_invitations(conn, form_id) -> int:
    """Invite every enrolled student to rate every lecturer (idempotent)."""
    ensure(conn)
    f = module_evaluation.form(conn, form_id)
    for lecturer in lecturers_for(conn, f["module_code"]):
        for student in _enrolled(conn, f["module_code"]):
            conn.execute("INSERT OR IGNORE INTO lecturer_eval_invitations (form_id, lecturer, "
                         "student_id) VALUES (?, ?, ?)", (form_id, lecturer["username"], student))
    return conn.execute("SELECT COUNT(*) FROM lecturer_eval_invitations WHERE form_id = ?",
                        (form_id,)).fetchone()[0]


def _student_forms(conn, student_id):
    return _dicts(conn.execute(
        "SELECT f.* FROM evaluation_forms f JOIN student_modules sm ON sm.module_code = "
        "f.module_code WHERE sm.student_id = ? AND LOWER(COALESCE(sm.status, '')) = 'enrolled' "
        "ORDER BY f.academic_year DESC, f.module_code", (str(student_id),)))


def student_lecturers(conn, student_id, now=None) -> list[dict]:
    """One row per lecturer on each of the student's module surveys."""
    ensure(conn)
    out = []
    for f in _student_forms(conn, student_id):
        current = module_evaluation.state(conn, f, now)
        if current == "open":
            sync_invitations(conn, f["id"])
        for lecturer in lecturers_for(conn, f["module_code"]):
            done = conn.execute("SELECT responded FROM lecturer_eval_invitations WHERE "
                                "form_id = ? AND lecturer = ? AND student_id = ?",
                                (f["id"], lecturer["username"], str(student_id))).fetchone()
            out.append({"form_id": f["id"], "module_code": f["module_code"],
                        "module_name": f["module_name"], "academic_year": f["academic_year"],
                        "lecturer": lecturer["username"], "name": lecturer["name"],
                        "closes": str(f.get("closes_at") or "")[:10],
                        "state": "answered" if done and done[0] else current})
    return out


def _check(conn, f, lecturer, student_id, now):
    if module_evaluation.state(conn, f, now) != "open":
        raise ValueError("Lecturer evaluation for this module is not open")
    if student_id not in _enrolled(conn, f["module_code"]):
        raise ValueError("Only students on the module can evaluate its lecturers")
    if lecturer not in {p["username"] for p in lecturers_for(conn, f["module_code"])}:
        raise ValueError("That lecturer does not teach this module")
    sync_invitations(conn, f["id"])
    if conn.execute("SELECT responded FROM lecturer_eval_invitations WHERE form_id = ? AND "
                    "lecturer = ? AND student_id = ?", (f["id"], lecturer, student_id)
                    ).fetchone()[0]:
        raise ValueError("You have already evaluated this lecturer for this module")


def _ratings(ratings):
    missing = [label for key, label, _d in CRITERIA if not ratings.get(key)]
    if missing:
        raise ValueError("Please rate: " + ", ".join(missing))
    for key in KEYS:
        value = ratings[key]
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 5:
            raise ValueError("Ratings run from 1 to 5")
    return [ratings[k] for k in KEYS]


def submit(conn, form_id, lecturer, student_id, ratings: dict, comments="", now=None) -> dict:
    """Record one student's evaluation of one lecturer on one module."""
    ensure(conn)
    f = module_evaluation.form(conn, form_id)
    student_id = str(student_id)
    _check(conn, f, lecturer, student_id, now)
    values = _ratings(ratings)
    comments = (comments or "").strip() or None
    eval_id = conn.execute(
        f"INSERT INTO lecturer_evaluations (form_id, module_code, academic_year, lecturer, "
        f"respondent, {', '.join(KEYS)}, comments, submitted_at) VALUES (?, ?, ?, ?, ?, "
        f"{', '.join('?' for _ in KEYS)}, ?, ?)",
        (form_id, f["module_code"], f["academic_year"], lecturer,
         f"tok-{secrets.token_hex(16)}", *values, comments,
         _now(now).date().isoformat())).lastrowid
    reason = module_evaluation.screen(conn, comments)
    if reason:
        conn.execute("INSERT INTO lecturer_eval_comment_reviews (evaluation_id, reason) "
                     "VALUES (?, ?)", (eval_id, reason))
    conn.execute("UPDATE lecturer_eval_invitations SET responded = 1 WHERE form_id = ? AND "
                 "lecturer = ? AND student_id = ?", (form_id, lecturer, student_id))
    return {"flagged": 1 if reason else 0}


# ── comment review ──────────────────────────────────────────────────────


def review_queue(conn) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute(
        "SELECT v.evaluation_id, v.reason, e.comments, e.module_code, e.lecturer, "
        "e.academic_year FROM lecturer_eval_comment_reviews v JOIN lecturer_evaluations e ON "
        "e.evaluation_id = v.evaluation_id WHERE v.status = 'pending' ORDER BY v.evaluation_id"))


def review_comment(conn, evaluation_id, release: bool, actor):
    ensure(conn)
    if not conn.execute("UPDATE lecturer_eval_comment_reviews SET status = ?, reviewed_by = ?, "
                        "reviewed_at = datetime('now') WHERE evaluation_id = ? AND "
                        "status = 'pending'", ("released" if release else "withheld", actor,
                                               evaluation_id)).rowcount:
        raise ValueError("That comment is not waiting for review")


# ── reminders ───────────────────────────────────────────────────────────


def _notify(conn, student_id, subject, body):
    from education_system.systems.university.infrastructure.email.messages_inbox import (
        deliver_inbox_message_on,
    )
    deliver_inbox_message_on(conn, student_id, subject, body)
    row = conn.execute("SELECT email_address FROM students WHERE student_id = ?",
                       (student_id,)).fetchone()
    return [(row[0], subject, body)] if row and row[0] and "@" in row[0] else []


def send_reminders(conn, now=None) -> dict:
    """One message per student listing the lecturers they have not rated on
    open module surveys, at most every ``REMIND_EVERY_DAYS``."""
    ensure(conn)
    now = _now(now)
    cutoff = (now.date() - timedelta(days=REMIND_EVERY_DAYS)).isoformat()
    due: dict[str, list] = {}
    for f in _dicts(conn.execute("SELECT * FROM evaluation_forms WHERE status = 'open'")):
        if module_evaluation.state(conn, f, now) != "open":
            continue
        sync_invitations(conn, f["id"])
        for lecturer, student in conn.execute(
                "SELECT lecturer, student_id FROM lecturer_eval_invitations WHERE form_id = ? AND "
                "responded = 0 AND (reminded_at IS NULL OR reminded_at <= ?)",
                (f["id"], cutoff)).fetchall():
            due.setdefault(student, []).append((f, lecturer))
    emails = []
    for student, items in due.items():
        lines = "\n".join(f"• {name_of(conn, lec)} ({f['module_code']}, closes "
                          f"{str(f['closes_at'])[:10]})" for f, lec in items)
        emails += _notify(conn, student, "Rate your lecturers",
                          f"You can still give anonymous feedback on:\n{lines}")
        for f, lecturer in items:
            conn.execute("UPDATE lecturer_eval_invitations SET reminded_at = ? WHERE form_id = ? "
                         "AND lecturer = ? AND student_id = ?",
                         (now.date().isoformat(), f["id"], lecturer, student))
    return {"sent": len(due), "emails": emails}


# ── reflections and "you said, we did" ──────────────────────────────────


def reflect(conn, form_id, lecturer, reflection, actions="", you_said="", we_did="",
            actor=None, admin=False, now=None) -> int:
    """The lecturer's reflection on a closed module survey's feedback."""
    ensure(conn)
    f = module_evaluation.form(conn, form_id)
    if not admin and actor != lecturer:
        raise ValueError("Only the lecturer writes their reflection")
    if module_evaluation.state(conn, f, now) in ("open", "scheduled"):
        raise ValueError("Reflect once the survey has closed")
    if not (reflection or "").strip():
        raise ValueError("Write a short reflection")
    return int(conn.execute("INSERT INTO lecturer_reflections (form_id, lecturer, reflection, "
                            "actions, you_said, we_did) VALUES (?, ?, ?, ?, ?, ?)",
                            (form_id, lecturer, reflection.strip(), actions or None,
                             you_said or None, we_did or None)).lastrowid)


def publish_reflection(conn, reflection_id, actor=None, admin=False) -> dict:
    """Send the "you said, we did" part to the module's invited students."""
    ensure(conn)
    row = _one(conn, "SELECT * FROM lecturer_reflections WHERE id = ?", (reflection_id,))
    if not row:
        raise ValueError("No such reflection")
    if not admin and actor != row["lecturer"]:
        raise ValueError("Only the lecturer publishes their response")
    if not (row["you_said"] and row["we_did"]):
        raise ValueError("Fill in 'you said' and 'we did' before publishing")
    f = module_evaluation.form(conn, row["form_id"])
    sync_invitations(conn, row["form_id"])
    conn.execute("UPDATE lecturer_reflections SET published = 1, published_at = "
                 "datetime('now') WHERE id = ?", (reflection_id,))
    emails, notified = [], 0
    who = name_of(conn, row["lecturer"])
    for (sid,) in conn.execute("SELECT student_id FROM lecturer_eval_invitations WHERE "
                               "form_id = ? AND lecturer = ?", (row["form_id"],
                                                                row["lecturer"])).fetchall():
        emails += _notify(conn, sid, f"{f['module_code']}: {who} — you said, we did",
                          f"You said: {row['you_said']}\n\nWe did: {row['we_did']}")
        notified += 1
    return {"notified": notified, "emails": emails}


def reflections(conn, lecturer, viewer, admin=False) -> list[dict]:
    ensure(conn)
    rows = _dicts(conn.execute(
        "SELECT r.*, f.module_code, f.academic_year FROM lecturer_reflections r JOIN "
        "evaluation_forms f ON f.id = r.form_id WHERE r.lecturer = ? ORDER BY r.id DESC",
        (lecturer,)))
    return [r for r in rows if access(conn, lecturer, viewer, admin, r["module_code"])]


def published_for_student(conn, student_id) -> list[dict]:
    ensure(conn)
    rows = _dicts(conn.execute(
        "SELECT DISTINCT r.id, r.lecturer, f.module_code, f.academic_year, r.you_said, r.we_did, "
        "r.published_at FROM lecturer_reflections r JOIN evaluation_forms f ON f.id = r.form_id "
        "JOIN lecturer_eval_invitations i ON i.form_id = r.form_id AND i.lecturer = r.lecturer "
        "WHERE r.published = 1 AND i.student_id = ? ORDER BY r.published_at DESC",
        (str(student_id),)))
    for r in rows:
        r["name"] = name_of(conn, r["lecturer"])
    return rows
