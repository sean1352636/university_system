"""Reports and analysis over the students a search finds (or everyone):
the reports the old Advanced Search window had, rebuilt on the current data
model and the search's permission scoping.

* **Demographics** — distributions (gender, age band, status, course, year,
  mode, fee status, entry route, nationality, ethnicity, disability, first
  language, start year) and a cross-tabulation of any two. Counts of 1 to
  ``SUPPRESS - 1`` are suppressed ("<10") so small groups cannot be singled
  out.
* **Performance** — per module: students with a result, mean mark, pass
  rate and grade bands (``module_grades``); attendance bands per student
  (``attendance_records``).
* **Data quality** — how many records lack each field.
* **Duplicates** — possible duplicate records (same name and date of birth,
  same university or personal email, same phone, or closely similar names
  with the same birthday), with staff decisions ("not a duplicate" /
  "duplicate") remembered so a reviewed pair is not shown again.
* **Insights** — at-risk counts by reason, registrations per month with a
  straight-line trend, each module's historical pass rate ("chance of
  passing" = the pass rate of past students, with how many), and expected
  completion years from each course's length. Trends and rates describe the
  past; nothing here scores an individual's future.
* **Search activity** and **system statistics** (administrators).
* :func:`generate` turns any report into a table (title, columns, rows,
  text) that :func:`export` writes in any ``table_export`` format; both
  are audited as ``report``.

Every report needs ``can_view_all`` (staff who can see every student).
Functions take an open connection and do not commit.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date

from education_system.systems.university.application.students import search
from education_system.systems.university.application.students.search import Viewer

SUPPRESS = 10
PASS_MARK = 40.0
_AGE_BAND = (f"CASE WHEN s.dob IS NULL OR s.dob = '' THEN 'Unknown' "
             f"WHEN {search._AGE} < 18 THEN 'Under 18' WHEN {search._AGE} <= 20 THEN '18-20' "
             f"WHEN {search._AGE} <= 24 THEN '21-24' WHEN {search._AGE} <= 29 THEN '25-29' "
             f"WHEN {search._AGE} <= 39 THEN '30-39' ELSE '40+' END")
_ED = "(SELECT {col} FROM ed_people e WHERE e.student_id = s.student_id AND e.deleted_at IS NULL " \
      "ORDER BY e.id DESC LIMIT 1)"
_SD = "(SELECT {col} FROM student_demographics d WHERE d.student_id = s.student_id LIMIT 1)"

#: key -> (label, SQL expression over students s, needs table)
DIMENSIONS = {
    "gender": ("Gender", "s.gender", None),
    "age_band": ("Age band", _AGE_BAND, None),
    "status": ("Status", search._STATUS, None),
    "course": ("Course", search._COURSE, None),
    "year_of_study": ("Year of study", "CAST(s.year_of_study AS TEXT)", None),
    "mode_of_study": ("Mode of study", "s.mode_of_study", None),
    "fee_status": ("Fee status", "s.fee_status", None),
    "entry_route": ("Entry route", "s.entry_route", None),
    "nationality": ("Nationality", "s.nationality", None),
    "start_year": ("Start year", "SUBSTR(COALESCE(NULLIF(s.enrollment_date, ''), "
                                 "s.registration_datetime), 1, 4)", None),
    "ethnicity": ("Ethnicity", f"COALESCE({_ED.format(col='e.ethnicity')}, "
                               f"{_SD.format(col='d.ethnicity')})", "ed"),
    "disability": ("Disability", _ED.format(col="e.disability"), "ed_people"),
    "first_language": ("First language", _SD.format(col="d.native_language"),
                       "student_demographics"),
}
QUALITY_FIELDS = (("email_address", "University email"), ("dob", "Date of birth"),
                  ("gender", "Gender"), ("nationality", "Nationality"), ("phone", "Phone"),
                  ("address", "Home address"), ("personal_email", "Personal email"),
                  ("emergency_contact", "Emergency contact"), ("course", "Course"),
                  ("year_of_study", "Year of study"), ("mode_of_study", "Mode of study"),
                  ("fee_status", "Fee status"), ("entry_route", "Entry route"),
                  ("enrollment_date", "Enrolment date"))
REPORTS = {
    "student_summary": "Student summary",
    "demographics": "Demographic profile",
    "crosstab": "Cross-tabulation",
    "module_enrolment": "Module enrolment",
    "performance": "Academic performance by module",
    "attendance": "Attendance bands",
    "data_quality": "Data quality",
    "duplicates": "Possible duplicate records",
    "at_risk": "At-risk students",
    "registrations": "Registrations per month",
    "module_pass_rates": "Module pass rates (historical)",
    "completion": "Expected completion years",
    "student_performance": "One student's performance",
    "search_activity": "Search activity (administrators)",
    "system": "System statistics (administrators)",
}
ADMIN_REPORTS = ("search_activity", "system")


def _require(viewer: Viewer):
    if not viewer.can_view_all:
        raise ValueError("Reports are for staff who can see every student")


def _admin(viewer: Viewer):
    if viewer.role not in search.ADMIN_ROLES:
        raise ValueError("Only an administrator can see this")


def _has(conn, table) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (table,)).fetchone() is not None


def available_dimensions(conn) -> dict:
    """The dimensions the database can answer (their table exists)."""
    out = {}
    for key, (label, _expr, needs) in DIMENSIONS.items():
        if needs == "ed" and not (_has(conn, "ed_people") and _has(conn, "student_demographics")):
            continue
        if needs and needs != "ed" and not _has(conn, needs):
            continue
        out[key] = label
    return out


def _dim(conn, key):
    if key not in available_dimensions(conn):
        raise ValueError(f"Unknown or unavailable dimension {key!r}")
    return DIMENSIONS[key]


def _scope(criteria, viewer):
    return search._where(criteria or {}, viewer)


def shown(count) -> str:
    """A count as it may be shown: small non-zero counts suppressed."""
    return f"<{SUPPRESS}" if 0 < count < SUPPRESS else str(count)


# ── demographics ────────────────────────────────────────────────────────


def distribution(conn, criteria, viewer: Viewer, key) -> dict:
    _require(viewer)
    search.ensure(conn)
    label, expr, _needs = _dim(conn, key)
    where, args = _scope(criteria, viewer)
    rows = conn.execute(f"SELECT COALESCE(NULLIF(TRIM({expr}), ''), 'Not recorded') AS v, "  # nosec B608
                        f"COUNT(*) FROM students s WHERE {where} GROUP BY v "
                        "ORDER BY COUNT(*) DESC, v", args).fetchall()
    total = sum(r[1] for r in rows)
    return {"key": key, "label": label, "total": total,
            "rows": [{"value": str(v), "count": n, "shown": shown(n),
                      "percent": None if 0 < n < SUPPRESS or not total
                      else round(100.0 * n / total, 1)} for v, n in rows]}


def demographics(conn, criteria, viewer: Viewer, keys=None) -> dict:
    keys = keys or list(available_dimensions(conn))
    parts = [distribution(conn, criteria, viewer, k) for k in keys]
    return {"total": parts[0]["total"] if parts else 0, "parts": parts}


def crosstab(conn, criteria, viewer: Viewer, row_key, col_key) -> dict:
    _require(viewer)
    search.ensure(conn)
    if row_key == col_key:
        raise ValueError("Choose two different dimensions")
    r_label, r_expr, _ = _dim(conn, row_key)
    c_label, c_expr, _ = _dim(conn, col_key)
    where, args = _scope(criteria, viewer)
    data = conn.execute(
        f"SELECT COALESCE(NULLIF(TRIM({r_expr}), ''), 'Not recorded'), "  # nosec B608
        f"COALESCE(NULLIF(TRIM({c_expr}), ''), 'Not recorded'), COUNT(*) FROM students s "
        f"WHERE {where} GROUP BY 1, 2", args).fetchall()
    cells = {(str(r), str(c)): n for r, c, n in data}
    rows = sorted({k[0] for k in cells})
    cols = sorted({k[1] for k in cells})
    row_totals = {r: sum(cells.get((r, c), 0) for c in cols) for r in rows}
    col_totals = {c: sum(cells.get((r, c), 0) for r in rows) for c in cols}
    return {"row_label": r_label, "col_label": c_label, "rows": rows, "cols": cols,
            "cells": {f"{r}\t{c}": shown(cells.get((r, c), 0)) for r in rows for c in cols},
            "row_totals": {r: shown(n) for r, n in row_totals.items()},
            "col_totals": {c: shown(n) for c, n in col_totals.items()},
            "total": sum(row_totals.values())}


# ── academic performance ────────────────────────────────────────────────


def _band(mark) -> str:
    if mark >= 70:
        return "70+"
    if mark >= 60:
        return "60-69"
    if mark >= 50:
        return "50-59"
    if mark >= PASS_MARK:
        return "40-49"
    return "Under 40"


def performance(conn, criteria, viewer: Viewer) -> dict:
    """Per module, for the matching students: results, mean, pass rate and
    grade bands."""
    _require(viewer)
    search.ensure(conn)
    where, args = _scope(criteria, viewer)
    marks = conn.execute(
        "SELECT mg.module_code, COALESCE(m.module_name, mg.module_code), mg.final_score FROM "  # nosec B608
        "module_grades mg LEFT JOIN modules m ON m.module_code = mg.module_code WHERE "
        f"mg.final_score IS NOT NULL AND mg.student_id IN (SELECT s.student_id FROM students s "
        f"WHERE {where})", args).fetchall()
    by_module: dict = defaultdict(list)
    names = {}
    for code, name, mark in marks:
        by_module[code].append(float(mark))
        names[code] = name
    modules = []
    for code, values in sorted(by_module.items()):
        bands = Counter(_band(v) for v in values)
        modules.append({"module_code": code, "module_name": names[code], "results": len(values),
                        "mean": round(sum(values) / len(values), 1),
                        "pass_rate": round(100.0 * sum(v >= PASS_MARK for v in values)
                                           / len(values), 1),
                        **{f"band {b}": bands.get(b, 0) for b in
                           ("70+", "60-69", "50-59", "40-49", "Under 40")}})
    every = [v for values in by_module.values() for v in values]
    return {"modules": modules, "results": len(every),
            "mean": round(sum(every) / len(every), 1) if every else None,
            "pass_rate": round(100.0 * sum(v >= PASS_MARK for v in every) / len(every), 1)
            if every else None}


def attendance(conn, criteria, viewer: Viewer) -> dict:
    """How many matching students fall in each attendance band."""
    _require(viewer)
    search.ensure(conn)
    where, args = _scope(criteria, viewer)
    rows = conn.execute(f"SELECT {search._ATTENDANCE} FROM students s WHERE {where}",  # nosec B608
                        args).fetchall()
    bands = Counter()
    for (pct,) in rows:
        if pct is None:
            bands["No attendance recorded"] += 1
        elif pct >= 90:
            bands["90% or more"] += 1
        elif pct >= 70:
            bands["70-89%"] += 1
        elif pct >= 50:
            bands["50-69%"] += 1
        else:
            bands["Under 50%"] += 1
    order = ("90% or more", "70-89%", "50-69%", "Under 50%", "No attendance recorded")
    return {"total": len(rows), "bands": [{"band": b, "students": bands.get(b, 0)}
                                          for b in order]}


def module_enrolment(conn, criteria, viewer: Viewer) -> list[dict]:
    """Current module enrolments of the matching students, per module."""
    _require(viewer)
    search.ensure(conn)
    where, args = _scope(criteria, viewer)
    rows = conn.execute(
        "SELECT sm.module_code, COALESCE(m.module_name, sm.module_code), COUNT(*) FROM "  # nosec B608
        "student_modules sm LEFT JOIN modules m ON m.module_code = sm.module_code WHERE "
        "LOWER(COALESCE(sm.status, 'enrolled')) = 'enrolled' AND sm.student_id IN (SELECT "
        f"s.student_id FROM students s WHERE {where}) GROUP BY sm.module_code ORDER BY 3 DESC, 1",
        args).fetchall()
    return [{"module_code": c, "module_name": n, "enrolled": k} for c, n, k in rows]


# ── data quality and duplicates ─────────────────────────────────────────


def data_quality(conn, criteria, viewer: Viewer) -> dict:
    _require(viewer)
    search.ensure(conn)
    where, args = _scope(criteria, viewer)
    columns = {r[1] for r in conn.execute("PRAGMA table_info(students)")}
    total = conn.execute(f"SELECT COUNT(*) FROM students s WHERE {where}", args).fetchone()[0]  # nosec B608
    fields = []
    for column, label in QUALITY_FIELDS:
        if column not in columns:
            continue
        missing = conn.execute(f"SELECT COUNT(*) FROM students s WHERE {where} AND "  # nosec B608
                               f"(s.{column} IS NULL OR TRIM(CAST(s.{column} AS TEXT)) = '')",
                               args).fetchone()[0]
        fields.append({"field": label, "missing": missing,
                       "percent": round(100.0 * missing / total, 1) if total else 0.0})
    fields.sort(key=lambda f: -f["missing"])
    return {"total": total, "fields": fields}


def _fold(text) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", str(text or "")).casefold()
    return re.sub(r"[^a-z]", "", "".join(c for c in text if not unicodedata.combining(c)))


def _pair(a, b):
    return (a, b) if str(a) <= str(b) else (b, a)


def _exact_groups(rows) -> dict:
    """Students sharing a name and birthday, an email address or a phone."""
    groups = defaultdict(list)
    for r in rows:
        if r[3]:
            groups[("same name and date of birth", _fold(r[1]), _fold(r[2]),
                    str(r[3])[:10])].append(r)
        for idx, label in ((4, "same university email"), (5, "same personal email")):
            if r[idx] and "@" in str(r[idx]):
                groups[(label, str(r[idx]).strip().lower())].append(r)
        digits = re.sub(r"\D", "", str(r[6] or ""))
        if len(digits) >= 7:
            groups[("same phone", digits[-10:])].append(r)
    return groups


_SCORES = {"same name and date of birth": 100, "same university email": 80,
           "same personal email": 80, "same phone": 60}


def _similar_pairs(rows):
    """(a, b, reason, score) for similar or reversed names sharing a birthday."""
    from difflib import SequenceMatcher
    by_dob = defaultdict(list)
    for r in rows:
        if r[3]:
            by_dob[str(r[3])[:10]].append(r)
    for members in by_dob.values():
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                fa, fb = _fold(f"{a[1]}{a[2]}"), _fold(f"{b[1]}{b[2]}")
                swapped = _fold(f"{b[2]}{b[1]}")
                if fa == fb:
                    continue            # exact same name: already an exact group
                if fa == swapped:
                    yield a, b, "names reversed, same date of birth", 95
                    continue
                ratio = max(SequenceMatcher(None, fa, fb).ratio(),
                            SequenceMatcher(None, fa, swapped).ratio())
                if ratio >= 0.8:
                    yield a, b, "similar name, same date of birth", round(ratio * 90)


def duplicates(conn, viewer: Viewer, include_reviewed=False) -> list[dict]:
    """Possible duplicate pairs across every (non-erased) student."""
    _require(viewer)
    search.ensure(conn)
    rows = conn.execute("SELECT student_id, first_name, last_name, dob, email_address, "
                        "personal_email, phone, course, status FROM students WHERE student_id "
                        "NOT LIKE 'ERASED-%'").fetchall()
    found: dict = {}

    def add(a, b, reason, score):
        key = _pair(a[0], b[0])
        if key[0] != key[1]:
            entry = found.setdefault(key, {"reasons": [], "score": 0})
            entry["reasons"].append(reason)
            entry["score"] = max(entry["score"], score)

    for key, members in _exact_groups(rows).items():
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                add(a, b, key[0], _SCORES[key[0]])
    for a, b, reason, score in _similar_pairs(rows):
        add(a, b, reason, score)
    reviewed = {(r[0], r[1]): (r[2], r[3]) for r in conn.execute(
        "SELECT student_a, student_b, decision, reviewed_by FROM student_duplicate_reviews")}
    info = {r[0]: r for r in rows}
    out = []
    for (a, b), entry in sorted(found.items(), key=lambda kv: -kv[1]["score"]):
        decision = reviewed.get((a, b))
        if decision and not include_reviewed:
            continue
        out.append({"student_a": a, "name_a": f"{info[a][1] or ''} {info[a][2] or ''}".strip(),
                    "student_b": b, "name_b": f"{info[b][1] or ''} {info[b][2] or ''}".strip(),
                    "reasons": "; ".join(dict.fromkeys(entry["reasons"])),
                    "score": entry["score"], "decision": decision[0] if decision else "",
                    "reviewed_by": decision[1] if decision else ""})
    return out


def review_duplicate(conn, viewer: Viewer, student_a, student_b, decision, note="") -> None:
    """Remember a decision on a pair. Merging a real duplicate stays a
    student-records task (transfer the history, then withdraw or erase)."""
    if not viewer.can_update:
        raise ValueError("You do not have permission to review duplicates")
    if decision not in ("not_duplicate", "duplicate"):
        raise ValueError("Decide 'not_duplicate' or 'duplicate'")
    search.ensure(conn)
    a, b = _pair(str(student_a), str(student_b))
    conn.execute("INSERT INTO student_duplicate_reviews (student_a, student_b, decision, note, "
                 "reviewed_by) VALUES (?, ?, ?, ?, ?) ON CONFLICT(student_a, student_b) DO "
                 "UPDATE SET decision = excluded.decision, note = excluded.note, "
                 "reviewed_by = excluded.reviewed_by, reviewed_at = datetime('now')",
                 (a, b, decision, str(note or "").strip() or None, viewer.username))
    search.record(conn, viewer.username, "report", None, 2,
                  f"duplicate review {a} / {b}: {decision}")


# ── insights ────────────────────────────────────────────────────────────


def at_risk(conn, criteria, viewer: Viewer) -> dict:
    """Active matching students with an average under 40, attendance under
    70%, or no current module enrolment — counted by reason."""
    _require(viewer)
    search.ensure(conn)
    where, args = _scope(criteria, viewer)
    rows = conn.execute(
        f"SELECT s.student_id, {search.FIELDS['name'].expr}, {search._COURSE}, "  # nosec B608
        f"{search._MARK}, {search._ATTENDANCE}, (SELECT COUNT(*) FROM student_modules sm WHERE "
        "sm.student_id = s.student_id AND LOWER(COALESCE(sm.status, 'enrolled')) = 'enrolled') "
        f"FROM students s WHERE {where} AND {search._STATUS} = 'Active'", args).fetchall()
    students, reasons = [], Counter()
    for sid, name, course, mark, att, modules in rows:
        why = []
        if mark is not None and mark < PASS_MARK:
            why.append(f"average mark {mark}")
        if att is not None and att < 70:
            why.append(f"attendance {att}%")
        if not modules:
            why.append("no current module enrolment")
        for w in why:
            reasons[w.split(" ")[0] if not w.startswith("no ") else "no enrolment"] += 1
        if why:
            students.append({"student_id": sid, "name": name, "course": course,
                             "average_mark": mark, "attendance": att, "reasons": "; ".join(why)})
    return {"active": len(rows), "at_risk": len(students),
            "by_reason": {"average under 40": reasons["average"],
                          "attendance under 70%": reasons["attendance"],
                          "no current enrolment": reasons["no enrolment"]},
            "students": students}


def _trend(points):
    """Least-squares slope and intercept over (x, y)."""
    n = len(points)
    if n < 2:
        return 0.0, (points[0][1] if points else 0.0)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    var = sum((x - mx) ** 2 for x, _ in points)
    slope = sum((x - mx) * (y - my) for x, y in points) / var if var else 0.0
    return slope, my - slope * mx


def registrations(conn, criteria, viewer: Viewer, months=24, ahead=3) -> dict:
    """Registrations per month over the last ``months``, and the straight-line
    trend continued ``ahead`` months (a trend, not a forecast of anyone)."""
    _require(viewer)
    search.ensure(conn)
    where, args = _scope(criteria, viewer)
    expr = "SUBSTR(COALESCE(NULLIF(s.registration_datetime, ''), s.enrollment_date), 1, 7)"
    counts = dict(conn.execute(f"SELECT {expr}, COUNT(*) FROM students s WHERE {where} AND "  # nosec B608
                               f"{expr} IS NOT NULL GROUP BY 1", args).fetchall())
    today = date.today()
    labels = []
    year, month = today.year, today.month
    for _ in range(months):
        labels.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    labels.reverse()
    series = [{"month": m, "registrations": int(counts.get(m, 0))} for m in labels]
    slope, intercept = _trend([(i, r["registrations"]) for i, r in enumerate(series)])
    trend = []
    year, month = today.year, today.month
    for k in range(1, ahead + 1):
        month += 1
        if month == 13:
            year, month = year + 1, 1
        trend.append({"month": f"{year:04d}-{month:02d}",
                      "trend": max(0.0, round(intercept + slope * (len(series) - 1 + k), 1))})
    return {"series": series, "trend": trend, "per_month_change": round(slope, 2)}


def module_pass_rates(conn, viewer: Viewer, minimum=5) -> list[dict]:
    """Each module's historical pass rate over every past result; modules
    with fewer than ``minimum`` results are marked as too few to say."""
    _require(viewer)
    rows = conn.execute(
        "SELECT mg.module_code, COALESCE(m.module_name, mg.module_code), COUNT(*), "
        "SUM(mg.final_score >= ?), AVG(mg.final_score) FROM module_grades mg LEFT JOIN modules "
        "m ON m.module_code = mg.module_code WHERE mg.final_score IS NOT NULL GROUP BY "
        "mg.module_code ORDER BY 1", (PASS_MARK,)).fetchall()
    return [{"module_code": c, "module_name": n, "results": k,
             "pass_rate": round(100.0 * p / k, 1) if k >= minimum else None,
             "mean": round(avg, 1) if k >= minimum else None,
             "note": "" if k >= minimum else f"fewer than {minimum} results"}
            for c, n, k, p, avg in rows]


def _years(duration) -> int | None:
    match = re.search(r"(\d+(?:\.\d+)?)", str(duration or ""))
    if not match:
        return None
    value = float(match.group(1))
    if "month" in str(duration).lower():
        value /= 12
    return max(1, round(value))


def completion(conn, criteria, viewer: Viewer) -> dict:
    """Expected completion year of current students: start year + the
    course's length (from ``courses.duration``)."""
    _require(viewer)
    search.ensure(conn)
    where, args = _scope(criteria, viewer)
    rows = conn.execute(
        f"SELECT s.student_id, {search._COURSE}, SUBSTR(COALESCE(NULLIF(s.enrollment_date, ''), "  # nosec B608
        "s.registration_datetime), 1, 4), (SELECT c.duration FROM courses c WHERE s.course IN "
        "(c.course_code, c.code, c.course_name, c.name) LIMIT 1) FROM students s WHERE "
        f"{where} AND {search._STATUS} IN ('Active', 'Registration Pending', 'Interrupted', "
        "'Deferred', 'Suspended')", args).fetchall()
    by_year, unknown = Counter(), 0
    for _sid, _course, start, duration in rows:
        years = _years(duration)
        if not years or not str(start or "").isdigit():
            unknown += 1
            continue
        by_year[int(start) + years] += 1
    return {"students": len(rows), "unknown": unknown,
            "by_year": [{"year": y, "students": n} for y, n in sorted(by_year.items())]}


def student_performance(conn, viewer: Viewer, student_id) -> dict:
    """One student's module results, attendance and enrolments."""
    _require(viewer)
    search.ensure(conn)
    row = conn.execute(f"SELECT s.student_id, {search.FIELDS['name'].expr}, {search._COURSE}, "  # nosec B608
                       f"{search._STATUS}, s.year_of_study, {search._MARK}, {search._ATTENDANCE} "
                       "FROM students s WHERE s.student_id = ? AND s.student_id NOT LIKE "
                       "'ERASED-%'", (str(student_id),)).fetchone()
    if not row:
        raise ValueError(f"No student {student_id}")
    results = [{"module_code": r[0], "module_name": r[1], "mark": r[2], "grade": r[3],
                "outcome": r[4], "attempt": r[5]} for r in conn.execute(
        "SELECT mg.module_code, COALESCE(m.module_name, mg.module_code), mg.final_score, "
        "mg.final_grade, mg.outcome, mg.attempt FROM module_grades mg LEFT JOIN modules m ON "
        "m.module_code = mg.module_code WHERE mg.student_id = ? ORDER BY mg.module_code",
        (str(student_id),))]
    enrolled = [r[0] for r in conn.execute(
        "SELECT module_code FROM student_modules WHERE student_id = ? AND LOWER(COALESCE(status, "
        "'enrolled')) = 'enrolled' ORDER BY module_code", (str(student_id),))]
    search.record(conn, viewer.username, "report", None, 1, f"student performance {student_id}")
    return {"student_id": row[0], "name": row[1], "course": row[2], "status": row[3],
            "year_of_study": row[4], "average_mark": row[5], "attendance": row[6],
            "results": results, "enrolled": enrolled}


# ── administrators ──────────────────────────────────────────────────────


def search_activity(conn, viewer: Viewer, days=90) -> dict:
    _admin(viewer)
    search.ensure(conn)
    since = f"-{int(days)} days"
    by_action = dict(conn.execute("SELECT action, COUNT(*) FROM student_search_audit WHERE "
                                  "at >= datetime('now', ?) GROUP BY action", (since,)).fetchall())
    by_user = [{"user": u, "actions": n} for u, n in conn.execute(
        "SELECT actor, COUNT(*) FROM student_search_audit WHERE at >= datetime('now', ?) GROUP "
        "BY actor ORDER BY 2 DESC LIMIT 20", (since,))]
    by_day = [{"day": d, "actions": n} for d, n in conn.execute(
        "SELECT SUBSTR(at, 1, 10), COUNT(*) FROM student_search_audit WHERE at >= "
        "datetime('now', ?) GROUP BY 1 ORDER BY 1", (since,))]
    import json
    common = Counter()
    for (crit,) in conn.execute("SELECT criteria_json FROM student_search_audit WHERE action = "
                                "'search' AND criteria_json IS NOT NULL AND at >= "
                                "datetime('now', ?)", (since,)):
        try:
            common[search.describe(json.loads(crit))] += 1
        except (ValueError, TypeError):
            continue
    return {"days": days, "by_action": by_action, "by_user": by_user, "by_day": by_day,
            "top_searches": [{"search": k, "times": n} for k, n in common.most_common(15)]}


def system_stats(conn, viewer: Viewer) -> dict:
    _admin(viewer)
    search.ensure(conn)
    counts = {}
    for label, sql in (
            ("Students", "SELECT COUNT(*) FROM students WHERE student_id NOT LIKE 'ERASED-%'"),
            ("Erased records", "SELECT COUNT(*) FROM students WHERE student_id LIKE 'ERASED-%'"),
            ("Modules", "SELECT COUNT(*) FROM modules"),
            ("Current module enrolments", "SELECT COUNT(*) FROM student_modules WHERE "
                                          "LOWER(COALESCE(status, 'enrolled')) = 'enrolled'"),
            ("Module results", "SELECT COUNT(*) FROM module_grades"),
            ("Attendance records", "SELECT COUNT(*) FROM attendance_records"),
            ("Saved searches", "SELECT COUNT(*) FROM student_saved_searches"),
            ("Scheduled reports", "SELECT COUNT(*) FROM student_report_schedules"),
            ("Open follow-ups", "SELECT COUNT(*) FROM student_followups WHERE status = 'open'"),
            ("Search audit entries", "SELECT COUNT(*) FROM student_search_audit")):
        try:
            counts[label] = conn.execute(sql).fetchone()[0]
        except Exception:
            counts[label] = None
    by_status = dict(conn.execute(f"SELECT {search._STATUS}, COUNT(*) FROM students s WHERE "  # nosec B608
                                  "s.student_id NOT LIKE 'ERASED-%' GROUP BY 1").fetchall())
    pages = conn.execute("PRAGMA page_count").fetchone()[0]
    size = conn.execute("PRAGMA page_size").fetchone()[0]
    check = conn.execute("PRAGMA quick_check(1)").fetchone()[0]
    return {"counts": counts, "by_status": by_status,
            "database_mb": round(pages * size / 1048576, 1), "integrity": check}


def optimise(conn, viewer: Viewer) -> str:
    """Refresh the query planner's statistics (``PRAGMA optimize``)."""
    _admin(viewer)
    conn.execute("PRAGMA optimize")
    search.record(conn, viewer.username, "report", None, None, "database optimise")
    return "Query statistics refreshed."


# ── one table per report, and export ────────────────────────────────────


def _table(title, columns, rows, text=None):
    from education_system.systems.university.infrastructure.data_management import table_export
    labels = {c: c.replace("_", " ").capitalize() for c in columns}
    return {"title": title, "columns": columns, "labels": labels, "rows": rows,
            "text": text or table_export.text_table(columns, [labels[c] for c in columns], rows,
                                                   title)}


def _r_student_summary(conn, title, criteria, viewer, options):
    result = search.search(conn, criteria or {}, viewer, page_size=search.MAX_EXPORT,
                           audit=False)
    return _table(title, result["columns"], result["rows"])


def _r_demographics(conn, title, criteria, viewer, options):
    parts = demographics(conn, criteria, viewer, options.get("keys"))["parts"]
    rows = [{"dimension": p["label"], "value": r["value"], "students": r["shown"],
             "percent": "" if r["percent"] is None else r["percent"]}
            for p in parts for r in p["rows"]]
    return _table(title, ["dimension", "value", "students", "percent"], rows)


def _r_crosstab(conn, title, criteria, viewer, options):
    ct = crosstab(conn, criteria, viewer, options.get("row") or "course",
                  options.get("col") or "status")
    rows = [{ct["row_label"]: r, **{c: ct["cells"][f"{r}\t{c}"] for c in ct["cols"]},
             "Total": ct["row_totals"][r]} for r in ct["rows"]]
    rows.append({ct["row_label"]: "Total", **ct["col_totals"], "Total": shown(ct["total"])})
    return _table(title, [ct["row_label"], *ct["cols"], "Total"], rows)


def _r_module_enrolment(conn, title, criteria, viewer, options):
    return _table(title, ["module_code", "module_name", "enrolled"],
                  module_enrolment(conn, criteria, viewer))


def _r_performance(conn, title, criteria, viewer, options):
    cols = ["module_code", "module_name", "results", "mean", "pass_rate", "band 70+",
            "band 60-69", "band 50-59", "band 40-49", "band Under 40"]
    return _table(title, cols, performance(conn, criteria, viewer)["modules"])


def _r_attendance(conn, title, criteria, viewer, options):
    return _table(title, ["band", "students"], attendance(conn, criteria, viewer)["bands"])


def _r_data_quality(conn, title, criteria, viewer, options):
    dq = data_quality(conn, criteria, viewer)
    return _table(f"{title} ({dq['total']} students)", ["field", "missing", "percent"],
                  dq["fields"])


def _r_duplicates(conn, title, criteria, viewer, options):
    return _table(REPORTS["duplicates"], ["student_a", "name_a", "student_b", "name_b",
                                          "reasons", "score", "decision"],
                  duplicates(conn, viewer, options.get("include_reviewed", False)))


def _r_at_risk(conn, title, criteria, viewer, options):
    risk = at_risk(conn, criteria, viewer)
    return _table(f"{title} ({risk['at_risk']} of {risk['active']} active)",
                  ["student_id", "name", "course", "average_mark", "attendance", "reasons"],
                  risk["students"])


def _r_registrations(conn, title, criteria, viewer, options):
    reg = registrations(conn, criteria, viewer)
    rows = [{**r, "trend": ""} for r in reg["series"]]
    rows += [{"month": t["month"], "registrations": "", "trend": t["trend"]}
             for t in reg["trend"]]
    return _table(f"{title} (trend {reg['per_month_change']:+} a month)",
                  ["month", "registrations", "trend"], rows)


def _r_module_pass_rates(conn, title, criteria, viewer, options):
    return _table(REPORTS["module_pass_rates"], ["module_code", "module_name", "results",
                                                 "pass_rate", "mean", "note"],
                  module_pass_rates(conn, viewer))


def _r_completion(conn, title, criteria, viewer, options):
    comp = completion(conn, criteria, viewer)
    return _table(f"{title} ({comp['unknown']} without a start year or course length)",
                  ["year", "students"], comp["by_year"])


def _r_student_performance(conn, title, criteria, viewer, options):
    sp = student_performance(conn, viewer, options.get("student_id"))
    average = "no results" if sp["average_mark"] is None else sp["average_mark"]
    attended = "none recorded" if sp["attendance"] is None else f"{sp['attendance']}%"
    head = (f"{sp['student_id']} {sp['name']} — {sp['course']} ({sp['status']}), "
            f"year {sp['year_of_study'] or '?'}; average {average}, attendance "
            f"{attended}; enrolled on {', '.join(sp['enrolled']) or 'nothing'}")
    return _table(head, ["module_code", "module_name", "mark", "grade", "outcome", "attempt"],
                  sp["results"])


def _r_search_activity(conn, title, criteria, viewer, options):
    act = search_activity(conn, viewer)
    return _table(REPORTS["search_activity"], ["search", "times"], act["top_searches"],
                  _activity_text(act))


def _r_system(conn, title, criteria, viewer, options):
    stats = system_stats(conn, viewer)
    rows = [{"measure": k, "value": v} for k, v in stats["counts"].items()]
    rows += [{"measure": f"Status: {k}", "value": v} for k, v in stats["by_status"].items()]
    rows += [{"measure": "Database size (MB)", "value": stats["database_mb"]},
             {"measure": "Integrity check", "value": stats["integrity"]}]
    return _table(REPORTS["system"], ["measure", "value"], rows)


def generate(conn, name, criteria, viewer: Viewer, **options) -> dict:
    """Any report in :data:`REPORTS` as ``{"title", "columns", "labels",
    "rows", "text"}``."""
    if name not in REPORTS:
        raise ValueError(f"Unknown report {name!r}")
    title = f"{REPORTS[name]} — {search.describe(criteria)}"
    return globals()[f"_r_{name}"](conn, title, criteria, viewer, options)


def _activity_text(act) -> str:
    lines = [f"Search activity, last {act['days']} days", ""]
    lines += [f"  {k}: {v}" for k, v in act["by_action"].items()] or ["  (none)"]
    lines += ["", "Most active:"] + [f"  {u['user']}: {u['actions']}" for u in act["by_user"]]
    lines += ["", "Most common searches:"] + [f"  {t['times']}× {t['search']}"
                                              for t in act["top_searches"]]
    return "\n".join(lines)


def export(conn, report: dict, viewer: Viewer, path, fmt=None, delimiter=",") -> int:
    """Write a generated report to ``path`` (format from ``fmt`` or the file
    name); audited."""
    from education_system.systems.university.infrastructure.data_management import table_export
    if not viewer.can_export:
        raise ValueError("You do not have permission to export reports")
    fmt = fmt or table_export.format_for(path)
    if fmt == "sql" and viewer.role not in search.ADMIN_ROLES:
        raise ValueError("Only an administrator can export SQL statements")
    n = table_export.write(path, report["columns"], report["rows"], fmt, title=report["title"],
                           labels=report["labels"], delimiter=delimiter, table_name="report")
    search.record(conn, viewer.username, "report", None, n, f"{report['title']} as {fmt} to {path}")
    return n
