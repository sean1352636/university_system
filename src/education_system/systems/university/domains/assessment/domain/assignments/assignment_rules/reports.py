"""Advanced Analytics figures and export, limited to the modules the member of
staff can see. Only current submissions count: earlier versions and withdrawn
work are left out."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta

from education_system.systems.university.domains.assessment.domain.assignments.assignment_rules.scope import (
    sql_filter,
)

PASS_MARK = 40.0
_CURRENT = ("COALESCE(s.is_final_submission, 1) = 1 AND COALESCE(s.status, '') <> 'withdrawn'")
PERFORMANCE_HEADINGS = ("Assignment", "Module", "Submissions", "Marked", "Average %", "Pass rate %")
SUBMISSION_HEADINGS = ("Assignment", "Module", "Due", "Submissions", "On time", "Late", "Withdrawn")
COMPARATIVE_HEADINGS = ("Module", "Assignments", "Submissions", "Average %", "Late %")


def period_range(conn, period, now=None) -> tuple[str, str, str]:
    """``(start, end, wording)``. ``semester`` is the latest term that has
    ended, or the past six months where no term is recorded."""
    now = now or datetime.now()
    today = now.strftime("%Y-%m-%d")
    if period == "semester":
        row = None
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'academic_terms'").fetchone():
            row = conn.execute("SELECT start_date, end_date, name FROM academic_terms "
                               "WHERE end_date < ? AND start_date IS NOT NULL "
                               "ORDER BY end_date DESC LIMIT 1", (today,)).fetchone()
        if row:
            return row[0], row[1], f"{row[2]} ({row[0]} to {row[1]})"
        start = (now - timedelta(days=182)).strftime("%Y-%m-%d")
        return start, today, f"the past six months ({start} to {today})"
    start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    return start, today, f"the last 30 days ({start} to {today})"


def _in_period(start, end) -> tuple[str, list]:
    return " AND date(a.due_date) BETWEEN ? AND ?", [start, end]


def _round(value):
    return round(value, 1) if value is not None else None


def performance(conn, modules, start, end) -> list[tuple]:
    clause, params = sql_filter(modules)
    when, dates = _in_period(start, end)
    rows = conn.execute(
        "SELECT a.title, a.module_code, COUNT(s.id), COUNT(s.grade), AVG(s.grade), "
        "SUM(CASE WHEN s.grade >= ? THEN 1 ELSE 0 END) FROM assignments a "
        f"LEFT JOIN assignment_submissions s ON s.assignment_id = a.id AND {_CURRENT} "
        f"WHERE 1 = 1{clause}{when} GROUP BY a.id ORDER BY a.due_date DESC",  # nosec B608
        [PASS_MARK, *params, *dates]).fetchall()
    return [(r[0], r[1], r[2], r[3], _round(r[4]), _round(100 * (r[5] or 0) / r[3]) if r[3] else None)
            for r in rows]


def submissions(conn, modules, start, end) -> list[tuple]:
    clause, params = sql_filter(modules)
    when, dates = _in_period(start, end)
    return [tuple(r) for r in conn.execute(
        "SELECT a.title, a.module_code, substr(a.due_date, 1, 16), "
        f"SUM(CASE WHEN s.id IS NOT NULL AND {_CURRENT} THEN 1 ELSE 0 END), "
        f"SUM(CASE WHEN s.id IS NOT NULL AND {_CURRENT} AND COALESCE(s.late_submission, 0) = 0 "
        "THEN 1 ELSE 0 END), "
        f"SUM(CASE WHEN s.id IS NOT NULL AND {_CURRENT} AND s.late_submission = 1 THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN s.status = 'withdrawn' THEN 1 ELSE 0 END) FROM assignments a "
        "LEFT JOIN assignment_submissions s ON s.assignment_id = a.id "
        f"WHERE 1 = 1{clause}{when} GROUP BY a.id ORDER BY a.due_date DESC",  # nosec B608
        [*params, *dates])]


def comparative(conn, modules, start, end) -> list[tuple]:
    clause, params = sql_filter(modules)
    when, dates = _in_period(start, end)
    rows = conn.execute(
        "SELECT a.module_code, COUNT(DISTINCT a.id), COUNT(s.id), AVG(s.grade), "
        "SUM(CASE WHEN s.late_submission = 1 THEN 1 ELSE 0 END) FROM assignments a "
        f"LEFT JOIN assignment_submissions s ON s.assignment_id = a.id AND {_CURRENT} "
        f"WHERE 1 = 1{clause}{when} GROUP BY a.module_code ORDER BY a.module_code",  # nosec B608
        [*params, *dates]).fetchall()
    return [(r[0], r[1], r[2], _round(r[3]), _round(100 * (r[4] or 0) / r[2]) if r[2] else None)
            for r in rows]


def all_sections(conn, modules, period, now=None) -> dict:
    start, end, wording = period_range(conn, period, now)
    return {"wording": wording,
            "performance": performance(conn, modules, start, end),
            "submissions": submissions(conn, modules, start, end),
            "comparative": comparative(conn, modules, start, end)}


_SECTIONS = (("Performance", "performance", PERFORMANCE_HEADINGS),
             ("Submissions", "submissions", SUBMISSION_HEADINGS),
             ("Comparison", "comparative", COMPARATIVE_HEADINGS))


def export(report: dict, path) -> str:
    """Write ``report`` to ``path``: a sheet per section for .xlsx, otherwise
    one CSV with the sections one after another. Returns the path."""
    path = str(path)
    if path.lower().endswith(".xlsx"):
        from openpyxl import Workbook
        book = Workbook()
        book.remove(book.active)
        for title, key, headings in _SECTIONS:
            sheet = book.create_sheet(title)
            sheet.append(list(headings))
            for row in report[key]:
                sheet.append([_safe_cell(v) for v in row])
        book.save(path)
        return path
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([f"Assignment analytics for {report['wording']}"])
        for title, key, headings in _SECTIONS:
            writer.writerow([])
            writer.writerow([title])
            writer.writerow(headings)
            writer.writerows([[_safe_cell(v) for v in row] for row in report[key]])
    return path


def _safe_cell(value):
    """Titles are typed by people; don't let one run as a spreadsheet formula."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value
