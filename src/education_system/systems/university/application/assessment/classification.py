"""UK undergraduate marking scale, module levels and degree classification.

The rest of Grade Tracking keeps its letter grades and GPA for the analytics
built on them; module results and degree outcomes use this scale.

Classification follows the common UK pattern: only Level 5 and Level 6
modules count, Level 6 weighted twice Level 5, each module weighted by its
credits (equally when credits are not recorded). A final average within
:data:`BORDERLINE_MARGIN` below a boundary is flagged for the board's
discretion; it is not raised automatically.
"""

from __future__ import annotations

import re

PASS_MARK = 40.0
BORDERLINE_MARGIN = 2.0
#: (lower bound, label), highest first.
UK_BANDS = (
    (70.0, "First"),
    (60.0, "2:1"),
    (50.0, "2:2"),
    (40.0, "Third"),
    (0.0, "Fail"),
)
#: Level -> weight in the final classification average.
LEVEL_WEIGHTS = {5: 1.0, 6: 2.0}

_YEAR_IN_CODE = re.compile(r"-Y(\d)\b", re.IGNORECASE)


def uk_band(mark: float | None) -> str | None:
    if mark is None:
        return None
    for floor, label in UK_BANDS:
        if mark >= floor:
            return label
    return "Fail"


def module_level(module_code: str | None, year: str | int | None = None) -> int | None:
    """FHEQ level of a module: year of study + 3 (Year 1 = Level 4).

    Read from ``modules.year`` when it is a number, otherwise from a
    ``-Y<n>`` segment in the module code (``ACC-Y2-3`` is Year 2).
    """
    try:
        y = int(str(year).strip())
        if 1 <= y <= 4:
            return y + 3
    except (TypeError, ValueError):
        pass
    match = _YEAR_IN_CODE.search(module_code or "")
    if match:
        return int(match.group(1)) + 3
    return None


def _module_rows(conn, student_id):
    return conn.execute(
        "SELECT mg.module_code, mg.final_score, mg.outcome, mg.status, mg.is_complete, "
        "       m.year, COALESCE(m.credits, 0) AS credits "
        "FROM module_grades mg LEFT JOIN modules m ON m.module_code = mg.module_code "
        "WHERE mg.student_id = ? AND mg.final_score IS NOT NULL",
        (str(student_id),)).fetchall()


def level_averages(conn, student_id) -> dict[int, dict]:
    """Credit-weighted average per level: {level: {average, credits, modules}}."""
    levels: dict[int, dict] = {}
    for row in _module_rows(conn, student_id):
        level = module_level(row[0], row[5])
        if level is None:
            continue
        weight = float(row[6]) or 1.0
        entry = levels.setdefault(level, {"total": 0.0, "weight": 0.0, "credits": 0.0, "modules": 0})
        entry["total"] += float(row[1]) * weight
        entry["weight"] += weight
        entry["credits"] += float(row[6])
        entry["modules"] += 1
    return {lvl: {"average": round(e["total"] / e["weight"], 2), "credits": e["credits"],
                  "modules": e["modules"]} for lvl, e in levels.items()}


def degree_classification(conn, student_id) -> dict:
    """The proposed honours classification from Level 5 and 6 results."""
    averages = level_averages(conn, student_id)
    counted = {lvl: v for lvl, v in averages.items() if lvl in LEVEL_WEIGHTS}
    if not counted:
        return {"levels": averages, "average": None, "classification": None,
                "borderline": False, "note": "No Level 5 or Level 6 results yet."}
    total = sum(v["average"] * LEVEL_WEIGHTS[lvl] for lvl, v in counted.items())
    weight = sum(LEVEL_WEIGHTS[lvl] for lvl in counted)
    average = round(total / weight, 2)
    band = uk_band(average)
    next_up = next((floor for floor, _ in reversed(UK_BANDS) if floor > average), None)
    borderline = next_up is not None and next_up - average <= BORDERLINE_MARGIN
    note = "" if len(counted) == len(LEVEL_WEIGHTS) else "Provisional: not all counting levels have results."
    return {"levels": averages, "average": average, "classification": band,
            "borderline": borderline, "note": note}


def compensation_candidates(conn, student_id, minimum_mark: float = 30.0,
                            maximum_credits: float | None = 40.0) -> list[dict]:
    """Failed modules a board could compensate: mark at least ``minimum_mark``,
    and the student's average at that level at least the pass mark."""
    averages = level_averages(conn, student_id)
    out = []
    used: dict[int, float] = {}
    rows = sorted(_module_rows(conn, student_id), key=lambda r: -float(r[1]))
    for row in rows:
        mark = float(row[1])
        if mark >= PASS_MARK or mark < minimum_mark:
            continue
        level = module_level(row[0], row[5])
        if level is None or averages.get(level, {}).get("average", 0) < PASS_MARK:
            continue
        credits = float(row[6])
        if maximum_credits is not None and credits and used.get(level, 0) + credits > maximum_credits:
            continue
        used[level] = used.get(level, 0) + credits
        out.append({"module_code": row[0], "mark": mark, "level": level, "credits": credits})
    return out
