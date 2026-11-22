"""What a student can see about their marking. Nothing about a mark, rubric or
annotation shows until the grade has been released."""

from __future__ import annotations

from datetime import datetime


def _has_table(conn, name) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (name,)).fetchone() is not None


def rubric_for_assignment(conn, assignment_id) -> dict | None:
    """The marking criteria, which students can read before they submit."""
    row = conn.execute("SELECT r.id, r.name, r.description, r.total_points FROM assignments a "
                       "JOIN rubrics r ON r.id = a.rubric_id WHERE a.id = ?",
                       (assignment_id,)).fetchone()
    if not row:
        return None
    criteria = conn.execute(
        "SELECT COALESCE(criterion_name, criteria_name), "
        "COALESCE(criteria_description, description, ''), max_points FROM rubric_criteria "
        "WHERE rubric_id = ? ORDER BY COALESCE(criterion_order, order_index, display_order, id)",
        (row[0],)).fetchall()
    return {"name": row[1], "description": row[2] or "", "total_points": row[3],
            "criteria": [{"name": c[0], "description": c[1], "max_points": c[2]}
                         for c in criteria]}


def save_rubric_scores(conn, submission_id, scores) -> None:
    """``scores``: (criterion id, name, score, maximum). Replaces earlier marks."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("DELETE FROM submission_rubric_scores WHERE submission_id = ?", (submission_id,))
    conn.executemany("INSERT INTO submission_rubric_scores (submission_id, criterion_id, "
                     "criterion_name, score, max_points, marked_at) VALUES (?, ?, ?, ?, ?, ?)",
                     [(submission_id, c, n, s, m, now) for c, n, s, m in scores])


def for_student(conn, submission_id, student_id) -> dict:
    """The feedback on the student's own submission. ``released`` is False
    until they may see it, and the marking fields are then left empty."""
    row = conn.execute(
        "SELECT s.student_id, s.status, s.grade, s.feedback, s.submission_date, s.file_name, "
        "s.late_submission, s.late_days, s.version_number, a.title, a.module_code, a.max_marks, "
        "a.grades_released_at FROM assignment_submissions s JOIN assignments a "
        "ON a.id = s.assignment_id WHERE s.id = ?", (submission_id,)).fetchone()
    if not row or str(row[0]) != str(student_id):
        raise ValueError("That isn't one of your submissions")
    released = row[2] is not None and (row[1] == "grade_released" or bool(row[12]))
    out = {"title": row[9], "module_code": row[10], "max_marks": row[11], "status": row[1],
           "submitted": row[4], "file_name": row[5], "late": bool(row[6]),
           "late_days": row[7] or 0, "version": row[8] or 1, "released": released,
           "marked": row[2] is not None, "grade": None, "feedback": "", "rubric": [],
           "annotations": []}
    if not released:
        return out
    out["grade"], out["feedback"] = row[2], row[3] or ""
    if _has_table(conn, "submission_rubric_scores"):
        out["rubric"] = [{"name": r[0], "score": r[1], "max_points": r[2]} for r in conn.execute(
            "SELECT criterion_name, score, max_points FROM submission_rubric_scores "
            "WHERE submission_id = ? ORDER BY criterion_id", (submission_id,))]
    if _has_table(conn, "submission_annotations"):
        out["annotations"] = [
            {"line": r[0], "category": r[1], "comment": r[2], "response": r[3] or ""}
            for r in conn.execute(
                "SELECT line_number, category, comment, student_response "
                "FROM submission_annotations WHERE submission_id = ? "
                "ORDER BY COALESCE(line_number, 0), id", (submission_id,))]
    return out


def as_text(info: dict) -> str:
    """The feedback window's wording."""
    lines = [f"{info['title']} ({info['module_code']})",
             f"Submitted: {info['submitted'] or '—'}   File: {info['file_name'] or '—'}   "
             f"Version: {info['version']}"]
    if info["late"]:
        lines.append(f"Late by {info['late_days']} day(s)")
    lines.append("")
    if not info["marked"]:
        lines.append("This work hasn't been marked yet.")
        return "\n".join(lines)
    if not info["released"]:
        lines.append("This work has been marked. The mark and feedback will appear here when "
                     "grades are released.")
        return "\n".join(lines)
    lines += [f"Mark: {info['grade']:g}%", "", "Feedback", "--------",
              info["feedback"] or "No written feedback was given."]
    if info["rubric"]:
        lines += ["", "Marks by criterion", "------------------"]
        lines += [f"{r['name']}: {r['score']:g} / {r['max_points']:g}" for r in info["rubric"]]
    if info["annotations"]:
        lines += ["", "Marker's comments on your work", "------------------------------"]
        for note in info["annotations"]:
            where = f"Line {note['line']}: " if note["line"] else ""
            lines.append(f"{where}[{note['category']}] {note['comment']}")
            if note["response"]:
                lines.append(f"    Your reply: {note['response']}")
    return "\n".join(lines)


def rubric_text(rubric: dict | None) -> str:
    if not rubric:
        return "No marking rubric has been set for this assignment."
    lines = [rubric["name"]]
    if rubric["description"]:
        lines.append(rubric["description"])
    lines.append("")
    if not rubric["criteria"]:
        lines.append("This rubric has no criteria yet.")
    for criterion in rubric["criteria"]:
        lines.append(f"{criterion['name']} (up to {criterion['max_points']:g} marks)")
        if criterion["description"]:
            lines.append(f"    {criterion['description']}")
    return "\n".join(lines)
