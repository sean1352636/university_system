"""The quizzes a student can sit, with what happened on earlier attempts."""

from __future__ import annotations

from datetime import datetime


def for_student(conn, student_id, now=None) -> list[dict]:
    """Published quizzes on the student's modules."""
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        "SELECT e.id, e.title, e.module_code, e.duration_minutes, e.end_time, e.max_attempts, "
        "(SELECT COUNT(*) FROM exam_portal_attempts t WHERE t.exam_id = e.id AND t.student_id = ?) "
        "FROM exam_portal_exams e JOIN assignments a ON a.id = e.assignment_id "
        "JOIN student_modules sm ON sm.module_code = e.module_code AND sm.student_id = ? "
        "WHERE e.status = 'published' AND a.is_active = 1 "
        "ORDER BY COALESCE(e.end_time, '9999')", (student_id, student_id)).fetchall()
    out = []
    for r in rows:
        left = max(int(r[5] or 1) - r[6], 0)
        closed = bool(r[4] and r[4] < stamp)
        state = "Closed" if closed else ("No attempts left" if not left else "Open")
        out.append({"exam_id": r[0], "title": r[1], "module_code": r[2], "minutes": r[3],
                    "closes": r[4], "attempts_left": left, "state": state})
    return out
