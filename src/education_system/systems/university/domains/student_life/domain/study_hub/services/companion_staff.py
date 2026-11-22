"""The staff side of the study companion: who may see a student's study
activity, the overview tutors see, and the study-plan slippage signal.

**Who sees what.** Administrators see every student. Other staff see the
students on modules they teach (``module_staff``, or ``modules.instructor``)
and the students in tutor groups they lead. A student sees only themselves.
A student who turns off *share with tutor* in their settings shows as "not
shared" with no detail, to everyone.

Staff see activity — plans, task completion, review counts, last active —
never the text of a student's cards or explanations.

**Slippage signal.** :func:`engagement_scan` raises an early-warning indicator
(``early_warning_indicators``, type ``study_plan_slippage``, severity low)
for a sharing student whose exam is within three weeks and who has missed at
least half of the last fortnight's plan tasks (three or more). It resolves
the indicator once they are back on track. Not using the companion is never
a signal — it is optional.

Functions take an open connection and do not commit.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.university.domains.student_life.domain.study_hub.services import (
    companion_reminders as reminders,
    study_context as ctx,
)

WINDOW_DAYS = 14
EXAM_HORIZON_DAYS = 21
MIN_MISSED = 3
INDICATOR = "study_plan_slippage"


def _today(today=None) -> date:
    if today is None:
        return date.today()
    return today if isinstance(today, date) else date.fromisoformat(str(today)[:10])


def _username(viewer) -> str:
    if not viewer:
        return ""
    if not isinstance(viewer, dict):
        viewer = getattr(viewer, "__dict__", {}) or {}
    return str(viewer.get("username") or "")


# ── access ──────────────────────────────────────────────────────────────


def visible_students(conn, viewer) -> set[str] | None:
    """Student ids ``viewer`` may see; ``None`` means everyone (admin)."""
    role = ctx.role_of(viewer)
    if role in ctx.ADMIN_ROLES:
        return None
    if role not in ctx.STAFF_ROLES:
        own = ctx.owner_id(viewer)
        return {own} if own else set()
    username = _username(viewer)
    if not username:
        return set()
    codes: set[str] = set()
    if ctx._has_table(conn, "module_staff"):
        codes |= {r[0] for r in conn.execute(
            "SELECT DISTINCT module_code FROM module_staff WHERE username = ?",
            (username,)).fetchall()}
    if ctx._has_table(conn, "modules") and "instructor" in ctx._columns(conn, "modules"):
        codes |= {r[0] for r in conn.execute(
            "SELECT module_code FROM modules WHERE instructor = ?", (username,)).fetchall()}
    students: set[str] = set()
    if codes and ctx._has_table(conn, "student_modules"):
        marks = ", ".join("?" * len(codes))
        students |= {str(r[0]) for r in conn.execute(
            "SELECT DISTINCT student_id FROM student_modules sm WHERE module_code IN (" + marks
            + ") AND " + ctx.enrolled_condition(conn), tuple(codes)).fetchall()}
    if ctx._has_table(conn, "tutor_groups") and ctx._has_table(conn, "tutor_group_members"):
        ids = set()
        row = conn.execute("SELECT id, email FROM users WHERE username = ?",
                           (username,)).fetchone()
        if row:
            ids.add(row[0])
            if row[1] and ctx._has_table(conn, "instructors"):
                ids |= {r[0] for r in conn.execute(
                    "SELECT id FROM instructors WHERE LOWER(email) = LOWER(?)",
                    (row[1],)).fetchall()}
        if ids:
            marks = ", ".join("?" * len(ids))
            students |= {str(r[0]) for r in conn.execute(
                "SELECT m.student_id FROM tutor_group_members m JOIN tutor_groups g "
                "ON g.group_id = m.group_id WHERE g.lead_tutor_id IN (" + marks + ") "
                "AND COALESCE(m.is_active, 1) = 1", tuple(ids)).fetchall()}
    return students


def can_view(conn, viewer, student_id) -> bool:
    if student_id is None:
        return False
    if ctx.owner_id(viewer) == str(student_id):
        return True
    visible = visible_students(conn, viewer)
    return visible is None or str(student_id) in visible


# ── overview ────────────────────────────────────────────────────────────


def _name(conn, student_id) -> str:
    if ctx._has_table(conn, "students"):
        row = conn.execute("SELECT TRIM(COALESCE(first_name, '') || ' ' || "
                           "COALESCE(last_name, '')) FROM students WHERE student_id = ?",
                           (str(student_id),)).fetchone()
        if row and row[0]:
            return row[0]
    return str(student_id)


def activity(conn, student_id, today=None) -> dict:
    """Study activity over the last fortnight, for staff and the slippage scan."""
    day = _today(today)
    start = (day - timedelta(days=WINDOW_DAYS)).isoformat()
    yesterday = (day - timedelta(days=1)).isoformat()
    sid = str(student_id)
    task = conn.execute(
        "SELECT SUM(CASE WHEN COALESCE(t.status, 'pending') = 'done' THEN 1 ELSE 0 END), "
        "       SUM(CASE WHEN COALESCE(t.status, 'pending') = 'pending' THEN 1 ELSE 0 END), "
        "       COUNT(*) FROM study_plan_tasks t JOIN study_plans p ON p.plan_id = t.plan_id "
        "WHERE p.student_id = ? AND COALESCE(p.status, 'Active') IN ('Active', 'Completed') "
        "AND t.scheduled_date BETWEEN ? AND ?", (sid, start, yesterday)).fetchone()
    done, missed, due = (int(v or 0) for v in task)
    plans = conn.execute(
        "SELECT COUNT(*), MIN(CASE WHEN end_date >= ? THEN end_date END) FROM study_plans "
        "WHERE student_id = ? AND COALESCE(status, 'Active') = 'Active'",
        (day.isoformat(), sid)).fetchone()
    reviews = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN quality >= 3 THEN 1 ELSE 0 END), MAX(reviewed_at) "
        "FROM flashcard_reviews WHERE student_id = ? AND reviewed_at >= ?",
        (sid, start)).fetchone()
    last_task = conn.execute(
        "SELECT MAX(t.completed_at) FROM study_plan_tasks t JOIN study_plans p "
        "ON p.plan_id = t.plan_id WHERE p.student_id = ?", (sid,)).fetchone()[0]
    last_review = conn.execute("SELECT MAX(reviewed_at) FROM flashcard_reviews "
                               "WHERE student_id = ?", (sid,)).fetchone()[0]
    last = max([v for v in (last_task, last_review) if v] or [None], key=lambda v: v or "")
    return {
        "active_plans": int(plans[0] or 0),
        "next_plan_exam": plans[1],
        "tasks_due": due,
        "tasks_done": done,
        "tasks_missed": missed,
        "completion_pct": round(100.0 * done / due, 1) if due else None,
        "cards_reviewed": int(reviews[0] or 0),
        "recall_pct": round(100.0 * (reviews[1] or 0) / reviews[0], 1) if reviews[0] else None,
        "last_active": str(last)[:16] if last else None,
    }


def overview(conn, viewer, module_code=None, today=None) -> list[dict]:
    """One row per companion user ``viewer`` may see (optionally only those
    on ``module_code``), most missed tasks first."""
    visible = visible_students(conn, viewer)
    users = reminders.companion_users(conn)
    if module_code and ctx._has_table(conn, "student_modules"):
        on_module = {str(r[0]) for r in conn.execute(
            "SELECT student_id FROM student_modules sm WHERE module_code = ? AND "
            + ctx.enrolled_condition(conn), (module_code,)).fetchall()}
        users = [u for u in users if u in on_module]
    rows = []
    for sid in users:
        if visible is not None and sid not in visible:
            continue
        shared = bool(reminders.settings(conn, sid)["share_with_tutor"])
        row = {"student_id": sid, "name": _name(conn, sid), "shared": shared}
        if shared:
            row.update(activity(conn, sid, today))
        rows.append(row)
    rows.sort(key=lambda r: (not r["shared"], -(r.get("tasks_missed") or 0), r["student_id"]))
    return rows


def student_detail(conn, viewer, student_id, today=None) -> dict:
    """What staff may see about one student's companion use."""
    if not can_view(conn, viewer, student_id):
        raise PermissionError("You can only see students you teach or tutor")
    sid = str(student_id)
    out = {"student_id": sid, "name": _name(conn, sid),
           "shared": bool(reminders.settings(conn, sid)["share_with_tutor"])}
    if not out["shared"] and ctx.owner_id(viewer) != sid:
        return out
    out.update(activity(conn, sid, today))
    cur = conn.execute(
        "SELECT p.plan_id, p.plan_name, p.course_id, p.end_date, p.status, "
        "COUNT(t.task_id) AS tasks, "
        "SUM(CASE WHEN COALESCE(t.status, 'pending') = 'done' THEN 1 ELSE 0 END) AS done "
        "FROM study_plans p LEFT JOIN study_plan_tasks t ON t.plan_id = p.plan_id "
        "WHERE p.student_id = ? GROUP BY p.plan_id ORDER BY p.end_date DESC", (sid,))
    names = [d[0] for d in cur.description]
    out["plans"] = [dict(zip(names, tuple(r))) for r in cur.fetchall()]
    cur = conn.execute(
        "SELECT deck_name, course_id, COUNT(*) AS cards, "
        "SUM(CASE WHEN COALESCE(suspended, 0) = 0 AND (next_review IS NULL OR next_review <= ?) "
        "THEN 1 ELSE 0 END) AS due FROM flashcards WHERE student_id = ? "
        "GROUP BY deck_name, course_id ORDER BY deck_name", (_today(today).isoformat(), sid))
    names = [d[0] for d in cur.description]
    out["decks"] = [dict(zip(names, tuple(r))) for r in cur.fetchall()]
    out["weak_modules"] = ctx.weak_modules(conn, sid)
    return out


# ── early-warning signal ────────────────────────────────────────────────


def slipping(conn, student_id, today=None) -> dict | None:
    """The slippage facts for a student, or ``None`` when on track."""
    day = _today(today)
    soon = conn.execute(
        "SELECT MIN(end_date) FROM study_plans WHERE student_id = ? "
        "AND COALESCE(status, 'Active') = 'Active' AND end_date BETWEEN ? AND ?",
        (str(student_id), day.isoformat(),
         (day + timedelta(days=EXAM_HORIZON_DAYS)).isoformat())).fetchone()[0]
    if not soon:
        return None
    a = activity(conn, student_id, day)
    if a["tasks_missed"] >= MIN_MISSED and a["tasks_due"] and a["tasks_missed"] * 2 >= a["tasks_due"]:
        return {"exam_date": soon, **a}
    return None


def engagement_scan(conn, today=None, actor="study companion") -> dict:
    """Raise or resolve ``study_plan_slippage`` indicators. ``{raised, resolved}``."""
    if not ctx._has_table(conn, "early_warning_indicators"):
        return {"raised": 0, "resolved": 0}
    day = _today(today)
    raised = resolved = 0
    for sid in reminders.companion_users(conn):
        if not ctx.is_student_record(conn, sid):
            continue
        open_row = conn.execute(
            "SELECT indicator_id FROM early_warning_indicators WHERE student_id = ? "
            "AND indicator_type = ? AND COALESCE(is_resolved, 0) = 0", (sid, INDICATOR)).fetchone()
        facts = (slipping(conn, sid, day)
                 if reminders.settings(conn, sid)["share_with_tutor"] else None)
        if facts and not open_row:
            conn.execute(
                "INSERT INTO early_warning_indicators (student_id, indicator_type, "
                "indicator_value, severity, notes) VALUES (?, ?, ?, 'low', ?)",
                (sid, INDICATOR, f"{facts['tasks_missed']}/{facts['tasks_due']}",
                 f"Missed {facts['tasks_missed']} of {facts['tasks_due']} study-plan tasks in the "
                 f"last {WINDOW_DAYS} days with an exam on {facts['exam_date']} "
                 f"(raised by {actor})."))
            raised += 1
        elif open_row and not facts:
            conn.execute(
                "UPDATE early_warning_indicators SET is_resolved = 1, resolved_at = ?, "
                "notes = COALESCE(notes, '') || ? WHERE indicator_id = ?",
                (day.isoformat(), f" Resolved {day.isoformat()}: back on track or no exam "
                 f"within {EXAM_HORIZON_DAYS} days.", open_row[0]))
            resolved += 1
    return {"raised": raised, "resolved": resolved}
