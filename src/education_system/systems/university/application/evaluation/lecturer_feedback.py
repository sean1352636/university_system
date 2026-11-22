"""Reading lecturer evaluations: per module and year, combined per year,
trend over years and comparison with the department.

A lecturer's results on a module are shown only once ``min_responses`` (the
module survey's threshold, default 5) students have rated them there, and
only to the people ``lecturer_evaluation.access`` allows - a module leader
sees only the modules they lead. Year totals, trends and comparisons are
built from shown results only.

Functions take an open connection and do not commit.
"""

from __future__ import annotations

import csv

from education_system.systems.university.application.evaluation import lecturer as rules

KEYS = rules.KEYS


def _pairs(conn, lecturer=None, academic_year=None) -> list[dict]:
    """(module survey, lecturer) pairs with their response count and
    threshold. Includes pairs with invitations but no answers yet."""
    sql = ("SELECT p.form_id, p.lecturer, f.module_code, f.academic_year, "
           "COALESCE(f.min_responses, 5) AS threshold, "
           "COALESCE(NULLIF(m.department, ''), m.course) AS department, "
           "(SELECT COUNT(*) FROM lecturer_evaluations e WHERE e.form_id = p.form_id AND "
           "e.lecturer = p.lecturer) AS responses, "
           "(SELECT COUNT(*) FROM lecturer_eval_invitations i WHERE i.form_id = p.form_id AND "
           "i.lecturer = p.lecturer) AS invited "
           "FROM (SELECT form_id, lecturer FROM lecturer_eval_invitations UNION "
           "SELECT form_id, lecturer FROM lecturer_evaluations) p "
           "JOIN evaluation_forms f ON f.id = p.form_id "
           "LEFT JOIN modules m ON m.module_code = f.module_code WHERE 1 = 1")
    args: list = []
    if lecturer:
        sql += " AND p.lecturer = ?"
        args.append(lecturer)
    if academic_year:
        sql += " AND f.academic_year = ?"
        args.append(academic_year)
    return rules._dicts(conn.execute(sql + " ORDER BY f.academic_year DESC, f.module_code",
                                     args))


def _means(conn, pairs) -> dict:
    """Mean of each criterion over the evaluations in ``pairs``."""
    if not pairs:
        return {}
    clause = " OR ".join("(form_id = ? AND lecturer = ?)" for _ in pairs)
    args = [v for p in pairs for v in (p["form_id"], p["lecturer"])]
    row = conn.execute(f"SELECT COUNT(*), {', '.join(f'AVG({k})' for k in KEYS)} FROM "
                       f"lecturer_evaluations WHERE {clause}", args).fetchone()
    if not row[0]:
        return {}
    return dict(n=row[0], **{k: round(v, 2) for k, v in zip(KEYS, row[1:])})


def _distribution(conn, pair) -> dict:
    out = {}
    for key in KEYS:
        counts = dict(conn.execute(f"SELECT {key}, COUNT(*) FROM lecturer_evaluations WHERE "
                                   f"form_id = ? AND lecturer = ? GROUP BY {key}",
                                   (pair["form_id"], pair["lecturer"])).fetchall())
        out[key] = {i: counts.get(i, 0) for i in range(1, 6)}
    return out


def _comments(conn, pair) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT e.comments FROM lecturer_evaluations e LEFT JOIN lecturer_eval_comment_reviews v "
        "ON v.evaluation_id = e.evaluation_id WHERE e.form_id = ? AND e.lecturer = ? AND "
        "COALESCE(e.comments, '') <> '' AND (v.evaluation_id IS NULL OR v.status = 'released') "
        "ORDER BY e.evaluation_id", (pair["form_id"], pair["lecturer"]))]


def _module_row(conn, pair):
    pair = dict(pair, withheld=pair["responses"] < pair["threshold"])
    if pair["withheld"]:
        return dict(pair, means={}, distribution={}, comments=[])
    return dict(pair, means=_means(conn, [pair]), distribution=_distribution(conn, pair),
                comments=_comments(conn, pair))


def _department_mean(conn, lecturer, year, departments):
    peers = [p for p in _pairs(conn, academic_year=year) if p["lecturer"] != lecturer
             and p["department"] in departments and p["responses"] >= p["threshold"]]
    means = _means(conn, peers)
    return {"overall": means.get("overall"), "lecturers": len({p["lecturer"] for p in peers})}


def results(conn, lecturer, viewer, admin=False, academic_year=None) -> dict:
    """Everything the viewer may see about a lecturer's feedback."""
    rules.ensure(conn)
    visible = [p for p in _pairs(conn, lecturer, academic_year)
               if rules.access(conn, lecturer, viewer, admin, p["module_code"])]
    if not visible and not rules.access(conn, lecturer, viewer, admin):
        raise ValueError("You cannot see this lecturer's feedback")
    modules = [_module_row(conn, p) for p in visible]
    shown = [p for p in visible if p["responses"] >= p["threshold"]]
    years = sorted({p["academic_year"] for p in visible}, reverse=True)
    by_year = {y: _means(conn, [p for p in shown if p["academic_year"] == y]) for y in years}
    trend = [{"academic_year": y, "responses": by_year[y].get("n", 0),
              "overall": by_year[y].get("overall")} for y in years]
    current = years[0] if years else None
    departments = {p["department"] for p in visible if p["academic_year"] == current}
    previous = next((t for t in trend[1:] if t["overall"] is not None), None)
    return {"lecturer": lecturer, "name": rules.name_of(conn, lecturer), "modules": modules,
            "by_year": by_year, "trend": trend, "academic_year": current,
            "comparison": {"last_year": previous["overall"] if previous else None,
                           "department": _department_mean(conn, lecturer, current, departments)
                           if current else {"overall": None, "lecturers": 0}}}


def export_csv(result, path) -> int:
    labels = dict((k, label) for k, label, _d in rules.CRITERIA)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["lecturer", "module", "year", "responses", "invited",
                         *[labels[k] for k in KEYS]])
        for m in result["modules"]:
            writer.writerow([result["lecturer"], m["module_code"], m["academic_year"],
                             m["responses"], m["invited"],
                             *[("hidden" if m["withheld"] else m["means"].get(k)) for k in KEYS]])
    return len(result["modules"])
