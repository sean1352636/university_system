"""A programme's structure, its curriculum map, its students and its results.

* **Structure** — the modules of each year (stage) of a course, from the
  same union of links the module catalogue uses (``course_curriculum``,
  ``course_module_map``, ``modules.course``), each with its designation
  (core / compulsory / optional, ``module_programme_designations``) and the
  stage's credit totals against the 120-credit year.
* **Curriculum map** — which modules introduce, develop and assess each
  programme learning outcome (``course_outcome_modules``), and the gaps:
  outcomes nothing assesses, modules that serve no outcome.
* **Cohort** — the students actually on the course, whether filed under its
  code or its name, with their year, status and programme registration.
  ``courses.current_enrollment`` is a stored counter that drifts (CS said 12
  with 10 students); :func:`live_counts` is the real figure.
* **Results** — per entry cohort: started, continuing, completed, withdrawn,
  continuation and completion rates; degree classifications and the
  good-honours rate from ratified awards; OfS B3 figures already computed by
  External Quality Assurance; survey results.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from education_system.systems.university.application.modules import enrolment as module_enrolment
from education_system.systems.university.application.programmes import record

YEAR_CREDITS = 120
GOOD_HONOURS = ("first", "2:1", "upper second", "first class")
_DONE = ("graduated", "completed", "awarded")
_LEFT = ("withdrawn", "transferred", "dismissed", "terminated")


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


# ── structure ───────────────────────────────────────────────────────────


def stages(conn, code) -> list[dict]:
    """``[{year, modules: [...], core_credits, optional_credits, issues}]``."""
    module_enrolment.ensure(conn)
    record._course(conn, code)
    years = {}
    for module, year in conn.execute(
            "SELECT module_code, year FROM course_curriculum WHERE course_code = ?", (code,)):
        years.setdefault(module, year)
    for module, year in conn.execute("SELECT module_code, year FROM modules WHERE course = ?",
                                     (code,)):
        years.setdefault(module, year)
    designated = module_enrolment.designations_for_course(conn, code)
    info = {r["module_code"]: r for r in _dicts(conn.execute(
        "SELECT module_code, module_name, credits, COALESCE(is_active, 1) AS active "
        "FROM modules"))}
    by_stage = {}
    for module, year in years.items():
        d = designated.get(module, {})
        stage = d.get("year_of_study") or _int(year)
        m = info.get(module, {})
        by_stage.setdefault(stage, []).append({
            "module_code": module, "module_name": m.get("module_name") or "",
            "credits": m.get("credits") or 0, "active": m.get("active", 1),
            "designation": d.get("category") or "not designated"})
    return [_stage_summary(stage, mods) for stage, mods in
            sorted(by_stage.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))]


def _int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _stage_summary(stage, mods):
    active = [m for m in mods if m["active"]]
    required = sum(m["credits"] for m in active if m["designation"] in ("core", "compulsory"))
    offered = sum(m["credits"] for m in active)
    issues = []
    if required > YEAR_CREDITS:
        issues.append(f"core + compulsory is {required} credits, more than {YEAR_CREDITS}")
    if offered < YEAR_CREDITS:
        issues.append(f"only {offered} credits on offer, a year needs {YEAR_CREDITS}")
    undesignated = sum(1 for m in active if m["designation"] == "not designated")
    if undesignated:
        issues.append(f"{undesignated} module(s) not designated core/compulsory/optional")
    if any(not m["credits"] for m in active):
        issues.append("some modules have no credit value")
    return {"year": stage, "modules": sorted(mods, key=lambda m: m["module_code"]),
            "required_credits": required, "offered_credits": offered, "issues": issues}


# ── curriculum map ──────────────────────────────────────────────────────


def programme_outcomes(conn, code) -> list[dict]:
    return _dicts(conn.execute("SELECT id, outcome_code, description FROM course_learning_outcomes "
                               "WHERE course_code = ? ORDER BY outcome_code, id", (code,)))


def map_outcome(conn, outcome_id, module_code, coverage, module_outcome_code=""):
    record.ensure(conn)
    if coverage not in record.schema.COVERAGE:
        raise ValueError(f"Coverage is one of: {', '.join(record.schema.COVERAGE)}")
    row = conn.execute("SELECT course_code FROM course_learning_outcomes WHERE id = ?",
                       (outcome_id,)).fetchone()
    if not row:
        raise ValueError("No such programme outcome")
    on_course = {m["module_code"] for s in stages(conn, row[0]) for m in s["modules"]}
    if module_code not in on_course:
        raise ValueError(f"{module_code} is not part of {row[0]}")
    if module_outcome_code and not conn.execute(
            "SELECT 1 FROM learning_outcomes WHERE module_code = ? AND outcome_code = ?",
            (module_code, module_outcome_code)).fetchone():
        raise ValueError(f"{module_code} has no outcome {module_outcome_code}")
    conn.execute("INSERT INTO course_outcome_modules (outcome_id, module_code, module_outcome_code, "
                 "coverage) VALUES (?, ?, ?, ?) ON CONFLICT(outcome_id, module_code, "
                 "module_outcome_code) DO UPDATE SET coverage = excluded.coverage",
                 (outcome_id, module_code, module_outcome_code or "", coverage))


def unmap(conn, mapping_id) -> bool:
    record.ensure(conn)
    return conn.execute("DELETE FROM course_outcome_modules WHERE id = ?",
                        (mapping_id,)).rowcount > 0


def curriculum_map(conn, code) -> dict:
    """``{outcomes, modules, cells: {(outcome_id, module): coverage}, mappings, gaps}``."""
    record.ensure(conn)
    outcomes = programme_outcomes(conn, code)
    modules = [m["module_code"] for s in stages(conn, code) for m in s["modules"] if m["active"]]
    mappings = _dicts(conn.execute(
        "SELECT m.id, m.outcome_id, m.module_code, m.module_outcome_code, m.coverage "
        "FROM course_outcome_modules m JOIN course_learning_outcomes o ON o.id = m.outcome_id "
        "WHERE o.course_code = ?", (code,)))
    rank = {c: i for i, c in enumerate(record.schema.COVERAGE)}
    cells = {}
    for m in mappings:
        key = (m["outcome_id"], m["module_code"])
        if key not in cells or rank[m["coverage"]] > rank[cells[key]]:
            cells[key] = m["coverage"]
    assessed = {o for (o, _m), c in cells.items() if c == "assessed"}
    used = {m for (_o, m) in cells}
    gaps = [f"{o['outcome_code'] or o['id']} is never assessed" for o in outcomes
            if o["id"] not in assessed]
    gaps += [f"{m} serves no programme outcome" for m in modules if m not in used]
    return {"outcomes": outcomes, "modules": modules, "cells": cells, "mappings": mappings,
            "gaps": gaps}


# ── cohort ──────────────────────────────────────────────────────────────


def cohort(conn, code) -> list[dict]:
    names = record.names_for(conn, code)
    marks = ", ".join("?" for _ in names)
    rows = _dicts(conn.execute(
        "SELECT s.student_id, TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) "
        "AS name, s.course AS filed_as, COALESCE(s.year_of_study, s.year) AS year_of_study, "
        "COALESCE(s.status, 'Active') AS status, s.mode_of_study, "
        "COALESCE(s.enrollment_date, s.registration_datetime) AS started "
        f"FROM students s WHERE s.course IN ({marks}) ORDER BY s.status, s.student_id", names))
    regs = {}
    try:
        for sid, status in conn.execute("SELECT student_id, status FROM programme_registrations "
                                        "WHERE programme_code = ? ORDER BY registration_id",
                                        (code,)):
            regs[sid] = status
    except Exception:
        regs = {}
    for r in rows:
        r["registration"] = regs.get(r["student_id"], "not registered")
    return rows


def name_fix_plan(conn) -> dict:
    """Students filed under a course *name* (or something that is no course).

    ``{'fix': [(student_id, filed_as, code)], 'unknown': [(student_id, filed_as)]}``
    """
    by_name, codes = {}, set()
    for code, name in conn.execute("SELECT COALESCE(NULLIF(course_code, ''), code), "
                                   "COALESCE(NULLIF(course_name, ''), name) FROM courses"):
        codes.add(code)
        if name:
            by_name[name.strip().lower()] = code
    fix, unknown = [], []
    for sid, course in conn.execute("SELECT student_id, course FROM students "
                                    "WHERE TRIM(COALESCE(course, '')) <> ''"):
        if course in codes:
            continue
        target = by_name.get(course.strip().lower())
        if target:
            fix.append((sid, course, target))
        else:
            unknown.append((sid, course))
    return {"fix": fix, "unknown": unknown}


def apply_name_fix(conn, plan) -> int:
    """File students under the course code instead of its name."""
    done = 0
    for sid, filed_as, code in plan["fix"]:
        done += conn.execute("UPDATE students SET course = ? WHERE student_id = ? AND course = ?",
                             (code, sid, filed_as)).rowcount
    return done


def live_counts(conn) -> dict:
    """``{code: (active students, stored counter)}`` for every course."""
    out = {}
    for code, stored in conn.execute("SELECT COALESCE(NULLIF(course_code, ''), code), "
                                     "current_enrollment FROM courses"):
        out[code] = (record.active_students(conn, code), stored or 0)
    return out


def refresh_counters(conn) -> int:
    """Set ``courses.current_enrollment`` to the real number. Returns rows changed."""
    changed = 0
    for code, (actual, stored) in live_counts(conn).items():
        if actual != stored:
            changed += conn.execute("UPDATE courses SET current_enrollment = ? WHERE "
                                    "COALESCE(NULLIF(course_code, ''), code) = ?",
                                    (actual, code)).rowcount
    return changed


# ── results ─────────────────────────────────────────────────────────────


def _bucket(status):
    s = str(status or "").strip().lower()
    return "completed" if s in _DONE else "left" if s in _LEFT else "continuing"


def cohort_outcomes(conn, code) -> list[dict]:
    """Per entry year: started, continuing, completed, left; continuation and
    completion rates (completion only once the course's duration has passed)."""
    duration = _int(str(record._course(conn, code).get("duration") or "3").split()[0]) or 3
    by_year = {}
    for r in cohort(conn, code):
        year = str(r["started"] or "")[:4]
        if year.isdigit():
            by_year.setdefault(year, []).append(_bucket(r["status"]))
    from datetime import date
    out = []
    for year, buckets in sorted(by_year.items(), reverse=True):
        n = len(buckets)
        done, left = buckets.count("completed"), buckets.count("left")
        finished = date.today().year - int(year) >= duration
        out.append({"entry_year": year, "started": n, "continuing": buckets.count("continuing"),
                    "completed": done, "left": left,
                    "continuation_pct": round((n - left) / n * 100, 1),
                    "completion_pct": round(done / n * 100, 1) if finished else None})
    return out


def classifications(conn, code) -> dict:
    try:
        rows = conn.execute("SELECT classification, COUNT(*) FROM ratified_student_awards "
                            "WHERE programme_code = ? AND COALESCE(status, '') <> 'superseded' "
                            "GROUP BY classification", (code,)).fetchall()
    except Exception:
        rows = []
    counts = {str(c or "unclassified"): n for c, n in rows}
    total = sum(counts.values())
    good = sum(n for c, n in counts.items() if any(g in c.lower() for g in GOOD_HONOURS))
    return {"counts": counts, "total": total,
            "good_honours_pct": round(good / total * 100, 1) if total else None}


def b3_metrics(conn, code) -> list[dict]:
    names = record.names_for(conn, code)
    try:
        return _dicts(conn.execute(
            f"SELECT cohort_year, metric_type, value_pct, numerator, denominator, computed_at "
            f"FROM ofs_b3_metrics WHERE course IN ({', '.join('?' for _ in names)}) "
            "ORDER BY cohort_year DESC, metric_type", names))
    except Exception:
        return []
