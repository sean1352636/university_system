"""Teaching history per member of staff and academic year
(``instructor_performance_history``), rebuilt from feedback that met its
anonymity threshold: the overall rating of modules they lead (module
surveys) and how students rated them by name (lecturer evaluations, and any
module-survey questions about them).

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from education_system.systems.university.application.evaluation import module as module_evaluation


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _module_form_scores(conn, academic_year):
    """Per module survey that met its threshold: leader, overall and the
    mean of each staff member's own questions."""
    from education_system.systems.university.application.modules import delivery as module_delivery
    out = []
    for f in _dicts(conn.execute("SELECT * FROM evaluation_forms WHERE academic_year = ?",
                                 (academic_year,))):
        n = conn.execute("SELECT COUNT(*) FROM eval_form_responses WHERE form_id = ?",
                         (f["id"],)).fetchone()[0]
        if n < (f.get("min_responses") or 5):
            continue
        staff = dict(conn.execute(
            "SELECT q.staff_username, AVG(a.rating_value) FROM eval_form_answers a JOIN "
            "eval_form_questions q ON q.id = a.question_id WHERE q.form_id = ? AND "
            "q.scope = 'staff' AND a.rating_value IS NOT NULL GROUP BY q.staff_username",
            (f["id"],)).fetchall())
        overall = conn.execute(
            "SELECT AVG(a.rating_value) FROM eval_form_answers a JOIN eval_form_questions q ON "
            "q.id = a.question_id WHERE q.form_id = ? AND q.question_text = ?",
            (f["id"], module_evaluation.OVERALL)).fetchone()[0]
        out.append({"leader": module_delivery.leader(conn, f["module_code"]),
                    "overall": overall, "staff": staff, "responses": n})
    return out


def refresh_instructor_history(conn, academic_year) -> int:
    """Rebuild ``instructor_performance_history`` for the year from module
    surveys that met their anonymity threshold. Returns rows written."""
    module_evaluation.ensure(conn)
    people: dict[str, dict] = {}
    for f in _module_form_scores(conn, academic_year):
        names = set(f["staff"]) | ({f["leader"]} if f["leader"] else set())
        for who in names:
            p = people.setdefault(who, {"overall": [], "teaching": [], "forms": 0,
                                        "responses": 0})
            p["forms"] += 1
            p["responses"] += f["responses"]
            if who == f["leader"] and f["overall"] is not None:
                p["overall"].append(f["overall"])
            if f["staff"].get(who) is not None:
                p["teaching"].append(f["staff"][who])
    _add_lecturer_evaluations(conn, academic_year, people)
    conn.execute("DELETE FROM instructor_performance_history WHERE academic_year = ?",
                 (academic_year,))
    for who, p in people.items():
        conn.execute("INSERT INTO instructor_performance_history (instructor_id, academic_year, "
                     "semester, avg_overall_rating, avg_teaching_effectiveness, "
                     "total_evaluations, total_responses) VALUES (?, ?, '', ?, ?, ?, ?)",
                     (who, academic_year, _avg(p["overall"]), _avg(p["teaching"]),
                      p["forms"], p["responses"]))
    return len(people)


def _add_lecturer_evaluations(conn, academic_year, people):
    """Lecturer evaluations count towards "about them" wherever a lecturer
    was rated by at least the module survey's threshold of students."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'lecturer_evaluations'"
                        ).fetchone() or "lecturer" not in {
            r[1] for r in conn.execute("PRAGMA table_info(lecturer_evaluations)")}:
        return
    for who, n, overall in conn.execute(
            "SELECT e.lecturer, COUNT(*), AVG(e.overall) FROM lecturer_evaluations e JOIN "
            "evaluation_forms f ON f.id = e.form_id WHERE e.academic_year = ? GROUP BY "
            "e.form_id, e.lecturer HAVING COUNT(*) >= COALESCE(MAX(f.min_responses), 5)",
            (academic_year,)).fetchall():
        p = people.setdefault(who, {"overall": [], "teaching": [], "forms": 0, "responses": 0})
        p["forms"] += 1
        p["responses"] += n
        p["teaching"].append(overall)


def _avg(values):
    return round(sum(values) / len(values), 2) if values else None


def instructor_history(conn, username=None) -> list[dict]:
    sql = "SELECT * FROM instructor_performance_history"
    args: tuple = ()
    if username:
        sql += " WHERE instructor_id = ?"
        args = (username,)
    return _dicts(conn.execute(sql + " ORDER BY academic_year DESC, instructor_id", args))
