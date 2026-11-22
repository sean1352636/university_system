"""Exam timetable: student clashes, draft/publish, and invigilation.

The scheduler only checked that a room was not double-booked. Nothing
noticed a student with two exams at once or three in a day, and every exam
was announced to students the moment it was created, so a timetable could
not be drafted, checked and released together.

Here a sitting starts as a draft; :func:`publish` refuses while it has room
double-bookings or student overlaps (heavy days are warnings), and only then
may the caller notify students and add it to the calendar. Invigilators are
allocated per sitting, checked against each other's sessions and against the
candidate ratio.

Functions take an open connection and do not commit.
"""

from __future__ import annotations

import math
from datetime import datetime

from education_system.systems.university.application.exams.results import roster

MAX_EXAMS_PER_DAY = 2
INVIGILATION_RATIO = 30  # candidates per invigilator
INVIGILATOR_ROLES = ("lead", "invigilator", "support")


class TimetableError(ValueError):
    """A timetable rule refused the action; the message is safe to show."""


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _exams(conn, where="1 = 1", params=()):
    cur = conn.execute(f"SELECT * FROM exams WHERE {where} ORDER BY date, start_time", params)  # nosec B608
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _overlaps(a, b) -> bool:
    return (a["date"] == b["date"]
            and not (a["end_time"] <= b["start_time"] or a["start_time"] >= b["end_time"]))


def _label(exam) -> str:
    return f"#{exam['id']} {exam['module_code']} {exam['date']} {exam['start_time']}-{exam['end_time']}"


# ── clashes ─────────────────────────────────────────────────────────────


def _by_student(conn, exams):
    sittings: dict[str, list[dict]] = {}
    for exam in exams:
        for sid in roster(conn, exam):
            sittings.setdefault(sid, []).append(exam)
    return sittings


def _student_problems(sid, mine):
    problems = []
    for i, a in enumerate(mine):
        for b in mine[i + 1:]:
            if _overlaps(a, b):
                problems.append({"student_id": sid, "kind": "overlap",
                                 "exams": [_label(a), _label(b)], "exam_ids": [a["id"], b["id"]]})
    per_day: dict[str, list[dict]] = {}
    for exam in mine:
        per_day.setdefault(exam["date"], []).append(exam)
    for day, items in per_day.items():
        if len(items) > MAX_EXAMS_PER_DAY:
            problems.append({"student_id": sid, "kind": "heavy_day",
                             "exams": [_label(e) for e in items], "exam_ids": [e["id"] for e in items]})
    return problems


def student_clashes(conn, exam_ids=None, from_date=None) -> list[dict]:
    """Every student overlap (two exams at once) and heavy day (more than
    :data:`MAX_EXAMS_PER_DAY` exams) across the timetable, drafts included.
    With ``exam_ids``, only problems involving those sittings."""
    exams = _exams(conn, "date >= ?", (from_date,)) if from_date else _exams(conn)
    out = []
    for sid, mine in _by_student(conn, exams).items():
        for problem in _student_problems(sid, mine):
            if exam_ids is None or set(problem["exam_ids"]) & set(exam_ids):
                out.append(problem)
    return out


def clashes_for_candidate_exam(conn, module_code, date, start_time, end_time, student_ids,
                               exclude_exam_id=None) -> list[dict]:
    """Check a sitting before it is saved: who would clash, and with what."""
    candidate = {"id": exclude_exam_id or 0, "module_code": module_code, "date": date,
                 "start_time": start_time, "end_time": end_time}
    others = [e for e in _exams(conn, "date = ?", (date,)) if e["id"] != exclude_exam_id]
    out = []
    for sid in student_ids:
        mine = [e for e in others if str(sid) in roster(conn, e)]
        overlapping = [e for e in mine if _overlaps(candidate, e)]
        if overlapping:
            out.append({"student_id": str(sid), "kind": "overlap",
                        "exams": [_label(e) for e in overlapping]})
        elif len(mine) + 1 > MAX_EXAMS_PER_DAY:
            out.append({"student_id": str(sid), "kind": "heavy_day",
                        "exams": [_label(e) for e in mine]})
    return out


def room_conflicts(conn, exam) -> list[str]:
    return [_label(e) for e in _exams(conn, "date = ? AND room = ? AND id <> ?",
                                      (exam["date"], exam["room"], exam["id"]))
            if exam.get("room") and _overlaps(exam, e)]


# ── draft / publish ─────────────────────────────────────────────────────


def drafts(conn) -> list[dict]:
    return _exams(conn, "COALESCE(status, 'published') = 'draft'")


def publish_blockers(conn, exam_id) -> list[str]:
    exams = _exams(conn, "id = ?", (exam_id,))
    if not exams:
        return [f"Exam {exam_id} not found."]
    exam = exams[0]
    blockers = [f"Room double-booked with {c}" for c in room_conflicts(conn, exam)]
    overlaps = [c for c in student_clashes(conn, [exam_id]) if c["kind"] == "overlap"]
    if overlaps:
        blockers.append(f"{len(overlaps)} student(s) have another exam at the same time")
    return blockers


def publish(conn, exam_ids, published_by=None, force=False) -> dict:
    """Publish draft sittings. Returns {"published": [ids], "blocked": {id: [reasons]}}.

    Sittings with room double-bookings or student overlaps stay in draft
    unless ``force``. The caller notifies students and adds the published
    sittings to the calendar.
    """
    published, blocked = [], {}
    for exam_id in exam_ids:
        reasons = publish_blockers(conn, exam_id)
        if reasons and not force:
            blocked[exam_id] = reasons
            continue
        conn.execute("UPDATE exams SET status = 'published', published_at = ?, published_by = ? "
                     "WHERE id = ? AND COALESCE(status, 'published') = 'draft'",
                     (_now(), published_by, exam_id))
        published.append(exam_id)
    return {"published": published, "blocked": blocked}


def unpublish(conn, exam_id) -> None:
    conn.execute("UPDATE exams SET status = 'draft' WHERE id = ?", (exam_id,))


def is_published(conn, exam_id) -> bool:
    row = conn.execute("SELECT COALESCE(status, 'published') FROM exams WHERE id = ?", (exam_id,)).fetchone()
    return bool(row and row[0] == "published")


# ── invigilation ────────────────────────────────────────────────────────


def assign_invigilator(conn, exam_id, staff_id, staff_name=None, role="invigilator", room=None):
    if role not in INVIGILATOR_ROLES:
        raise TimetableError(f"Role must be one of {', '.join(INVIGILATOR_ROLES)}.")
    exam = _exams(conn, "id = ?", (exam_id,))
    if not exam:
        raise TimetableError(f"Exam {exam_id} not found.")
    busy = [e for e in invigilator_sessions(conn, staff_id) if e["id"] != exam_id and _overlaps(exam[0], e)]
    if busy:
        raise TimetableError(f"{staff_name or staff_id} is already invigilating {_label(busy[0])}.")
    conn.execute("INSERT INTO exam_invigilators (exam_id, staff_id, staff_name, role, room, created_at) "
                 "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (exam_id, staff_id) DO UPDATE SET "
                 "role = excluded.role, room = excluded.room, staff_name = excluded.staff_name",
                 (exam_id, str(staff_id), staff_name, role, room or exam[0].get("room"), _now()))


def remove_invigilator(conn, exam_id, staff_id) -> None:
    conn.execute("DELETE FROM exam_invigilators WHERE exam_id = ? AND staff_id = ?", (exam_id, str(staff_id)))


def invigilators(conn, exam_id) -> list[dict]:
    cur = conn.execute("SELECT staff_id, staff_name, role, room FROM exam_invigilators "
                       "WHERE exam_id = ? ORDER BY role, staff_name", (exam_id,))
    return [dict(zip(("staff_id", "staff_name", "role", "room"), r)) for r in cur.fetchall()]


def invigilator_sessions(conn, staff_id) -> list[dict]:
    return _exams(conn, "id IN (SELECT exam_id FROM exam_invigilators WHERE staff_id = ?)", (str(staff_id),))


def staffing_report(conn, from_date=None) -> list[dict]:
    """Per sitting: candidates, invigilators, how many are needed, and gaps."""
    report = []
    for exam in (_exams(conn, "date >= ?", (from_date,)) if from_date else _exams(conn)):
        candidates = len(roster(conn, exam))
        staff = invigilators(conn, exam["id"])
        needed = max(1, math.ceil(candidates / INVIGILATION_RATIO)) if candidates else 0
        issues = []
        if len(staff) < needed:
            issues.append(f"needs {needed - len(staff)} more invigilator(s)")
        if staff and not any(s["role"] == "lead" for s in staff):
            issues.append("no lead invigilator")
        report.append({"exam_id": exam["id"], "label": _label(exam), "candidates": candidates,
                       "invigilators": len(staff), "needed": needed, "issues": issues})
    return report
