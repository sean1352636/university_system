"""Peer review questions and the dashboard's three lists. Students see who
reviewed them only when the review wasn't anonymous."""

from __future__ import annotations

DEFAULT_CRITERIA = ("Content Quality", "Organization", "Clarity", "Creativity")
MAX_SCORE = 5


def criteria_for_assignment(conn, assignment_id) -> list[str]:
    """The questions the lecturer set; the standard four if they set none."""
    rows = conn.execute(
        "SELECT t.criteria_name FROM peer_review_config c JOIN peer_review_criteria_templates t "
        "ON t.config_id = c.id WHERE c.assignment_id = ? ORDER BY t.order_index, t.id",
        (assignment_id,)).fetchall()
    return [r[0] for r in rows] or list(DEFAULT_CRITERIA)


def criteria_for_review(conn, review_id) -> list[str]:
    row = conn.execute("SELECT assignment_id FROM peer_reviews WHERE id = ?",
                       (review_id,)).fetchone()
    return criteria_for_assignment(conn, row[0]) if row else list(DEFAULT_CRITERIA)


def save_criteria(conn, assignment_id, criteria, is_anonymous=True) -> None:
    """Store the questions typed on the setup screen."""
    row = conn.execute("SELECT id FROM peer_review_config WHERE assignment_id = ?",
                       (assignment_id,)).fetchone()
    if row:
        config_id = row[0]
        conn.execute("UPDATE peer_review_config SET is_anonymous = ? WHERE id = ?",
                     (1 if is_anonymous else 0, config_id))
    else:
        config_id = conn.execute(
            "INSERT INTO peer_review_config (assignment_id, is_anonymous) VALUES (?, ?)",
            (assignment_id, 1 if is_anonymous else 0)).lastrowid
    conn.execute("DELETE FROM peer_review_criteria_templates WHERE config_id = ?", (config_id,))
    conn.executemany("INSERT INTO peer_review_criteria_templates (config_id, criteria_name, "
                     "max_score, order_index) VALUES (?, ?, ?, ?)",
                     [(config_id, name, MAX_SCORE, i) for i, name in enumerate(criteria)])


def _reviews(conn, where, params) -> list[tuple]:
    return conn.execute(
        "SELECT pr.id, a.title, a.module_code, pr.status, pr.overall_score, pr.review_text, "
        "pr.review_date, COALESCE(pr.is_anonymous, 1), pr.reviewer_id, "
        "st.first_name, st.last_name FROM peer_reviews pr "
        "JOIN assignments a ON a.id = pr.assignment_id "
        "LEFT JOIN students st ON st.student_id = pr.reviewer_id "
        f"WHERE {where} ORDER BY pr.id DESC", params).fetchall()  # nosec B608


def completed_by(conn, student_id) -> list[dict]:
    return [{"id": r[0], "title": r[1], "module_code": r[2], "score": r[4], "date": r[6]}
            for r in _reviews(conn, "pr.reviewer_id = ? AND pr.status = 'completed'",
                              (student_id,))]


def pending_for(conn, student_id) -> list[dict]:
    return [{"id": r[0], "title": r[1], "module_code": r[2]}
            for r in _reviews(conn, "pr.reviewer_id = ? AND pr.status = 'pending'",
                              (student_id,))]


def results_for(conn, student_id) -> list[dict]:
    """Reviews other students completed about this student's work."""
    out = []
    for r in _reviews(conn, "pr.reviewee_id = ? AND pr.status = 'completed'", (student_id,)):
        name = "Anonymous" if r[7] else f"{r[9] or ''} {r[10] or ''}".strip() or "A student"
        scores = conn.execute("SELECT criteria_name, score FROM peer_review_criteria "
                              "WHERE review_id = ? ORDER BY id", (r[0],)).fetchall()
        out.append({"id": r[0], "title": r[1], "module_code": r[2], "score": r[4],
                    "comments": r[5] or "", "date": r[6], "reviewer": name,
                    "scores": [{"name": s[0], "score": s[1]} for s in scores]})
    return out


def summary_by_assignment(conn, modules) -> list[dict]:
    """For staff: how far each assignment's peer reviews have got."""
    from education_system.systems.university.domains.assessment.domain.assignments.assignment_rules.scope import (
        sql_filter,
    )
    clause, params = sql_filter(modules)
    rows = conn.execute(
        "SELECT a.title, a.module_code, COUNT(pr.id), "
        "SUM(CASE WHEN pr.status = 'completed' THEN 1 ELSE 0 END), AVG(pr.overall_score) "
        "FROM peer_reviews pr JOIN assignments a ON a.id = pr.assignment_id "
        f"WHERE 1 = 1{clause} GROUP BY a.id ORDER BY a.due_date DESC", params).fetchall()  # nosec B608
    return [{"title": r[0], "module_code": r[1], "total": r[2], "completed": r[3] or 0,
             "average": r[4]} for r in rows]
