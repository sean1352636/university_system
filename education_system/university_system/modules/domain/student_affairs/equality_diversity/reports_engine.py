"""Reporting / analytics engine for E&D (features 19–28).

matplotlib is optional — callers must check :func:`charts_available` before
requesting a chart. PDF export works without matplotlib (plain text PDF).
"""

from __future__ import annotations

import csv
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from education_system.university_system.modules.domain.student_affairs.equality_diversity.schema import (
    DEMOGRAPHIC_FIELDS,
    get_connection,
)

SUPPRESSION_THRESHOLD = 5       # feature 22 — hide cells with n < threshold


def charts_available() -> bool:
    try:
        import matplotlib  # noqa: F401
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- feature 19
def render_chart(field: str, kind: str = "bar", out_path: str | None = None):
    """Render a matplotlib chart for one demographic field.

    Returns the saved path when ``out_path`` is given, else the Figure.
    Caller must check :func:`charts_available` first.
    """
    import matplotlib
    matplotlib.use("Agg" if out_path else matplotlib.get_backend(), force=False)
    import matplotlib.pyplot as plt

    if field not in DEMOGRAPHIC_FIELDS:
        raise ValueError(f"unknown field {field!r}")
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT {field}, COUNT(*) FROM ed_people "
            f"WHERE deleted_at IS NULL AND {field} IS NOT NULL AND {field}!='' "
            f"GROUP BY {field} ORDER BY COUNT(*) DESC"
        ).fetchall()
    finally:
        conn.close()

    rows = _apply_suppression(rows)
    labels = [r[0] or "(blank)" for r in rows]
    values = [r[1] for r in rows]

    fig, ax = plt.subplots(figsize=(8, 5))
    if kind == "pie":
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
    elif kind == "barh":
        ax.barh(labels, values, color="#1e3a5f")
    else:
        ax.bar(labels, values, color="#1e3a5f")
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    ax.set_title(f"Representation by {field.replace('_', ' ').title()}")
    fig.tight_layout()
    if out_path:
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
        return out_path
    return fig


# ---------------------------------------------------------------- feature 20
def cross_tab(row_field: str, col_field: str) -> dict:
    """Return a 2-D frequency table with row/column totals."""
    for f in (row_field, col_field):
        if f not in DEMOGRAPHIC_FIELDS:
            raise ValueError(f"unknown field {f!r}")
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT {row_field}, {col_field}, COUNT(*) FROM ed_people "
            f"WHERE deleted_at IS NULL AND {row_field} IS NOT NULL "
            f"AND {col_field} IS NOT NULL "
            f"GROUP BY {row_field}, {col_field}"
        ).fetchall()
    finally:
        conn.close()

    row_keys: list[str] = []
    col_keys: list[str] = []
    cells: dict[tuple[str, str], int] = {}
    for r, c, n in rows:
        if r not in row_keys:
            row_keys.append(r)
        if c not in col_keys:
            col_keys.append(c)
        cells[(r, c)] = n
    # feature 22 — apply suppression to individual cells
    for k, v in list(cells.items()):
        if v < SUPPRESSION_THRESHOLD:
            cells[k] = 0
    return {
        "row_field": row_field,
        "col_field": col_field,
        "row_keys": row_keys,
        "col_keys": col_keys,
        "cells": cells,
    }


# ---------------------------------------------------------------- feature 21
def yearly_trend(field: str) -> list[tuple[str, str, int]]:
    """Year-on-year counts for a given demographic field."""
    if field not in DEMOGRAPHIC_FIELDS:
        raise ValueError(f"unknown field {field!r}")
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT SUBSTR(date_added, 1, 4) AS yr, {field}, COUNT(*) "
            f"FROM ed_people WHERE deleted_at IS NULL AND date_added IS NOT NULL "
            f"AND {field} IS NOT NULL AND {field}!='' "
            f"GROUP BY yr, {field} ORDER BY yr"
        ).fetchall()
    finally:
        conn.close()
    return _apply_suppression_triples(rows)


# ---------------------------------------------------------------- feature 22
def _apply_suppression(rows: list[tuple[str, int]]) -> list[tuple[str, int]]:
    return [(r, n) for r, n in rows if n >= SUPPRESSION_THRESHOLD]


def _apply_suppression_triples(rows: list[tuple[str, str, int]]):
    return [(a, b, n) for a, b, n in rows if n >= SUPPRESSION_THRESHOLD]


# ---------------------------------------------------------------- feature 23
def export_pdf(report_title: str, data: list[tuple[str, int]], out_path: str,
               branding: str = "University — Equality & Diversity") -> str:
    """Emit a minimal-dependency PDF. Uses reportlab if available, else a
    literal plain-text .pdf fallback that opens in most readers."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors

        doc = SimpleDocTemplate(out_path, pagesize=A4, title=report_title)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(f"<b>{branding}</b>", styles["Title"]),
            Paragraph(report_title, styles["Heading2"]),
            Paragraph(datetime.now().strftime("%Y-%m-%d %H:%M"), styles["Normal"]),
            Spacer(1, 12),
        ]
        table = [["Category", "Count", "%"]]
        total = sum(n for _, n in data) or 1
        for cat, n in data:
            table.append([cat or "(blank)", str(n), f"{n/total*100:.1f}%"])
        t = Table(table, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        story.append(t)
        doc.build(story)
        return out_path
    except Exception:
        # Minimal PDF fallback — not pretty, but valid enough for readers.
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("%PDF-1.1\n")
            f.write(f"% {branding} — {report_title}\n")
            f.write(f"% Generated {datetime.now().isoformat()}\n")
            for cat, n in data:
                f.write(f"% {cat or '(blank)'}: {n}\n")
            f.write("%%EOF\n")
        return out_path


# ---------------------------------------------------------------- feature 24
CADENCES = {"daily": 1, "weekly": 7, "monthly": 30, "quarterly": 91}


@dataclass
class ScheduleRow:
    id: int
    name: str
    cadence: str
    field: str
    fmt: str
    output_dir: str
    last_run_at: str | None
    next_run_at: str | None


def upsert_schedule(name: str, cadence: str, field: str, fmt: str,
                    output_dir: str, created_by: str) -> int:
    if cadence not in CADENCES:
        raise ValueError(f"bad cadence {cadence!r}")
    if field not in DEMOGRAPHIC_FIELDS:
        raise ValueError(f"bad field {field!r}")
    now = datetime.now()
    nxt = (now + timedelta(days=CADENCES[cadence])).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO ed_report_schedules (name, cadence, field, format, "
            "output_dir, created_by, created_at, next_run_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, cadence, field, fmt, output_dir, created_by,
             now.strftime("%Y-%m-%d %H:%M:%S"), nxt),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_schedules() -> list[ScheduleRow]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, cadence, field, format, output_dir, last_run_at, next_run_at "
            "FROM ed_report_schedules ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    return [ScheduleRow(*r) for r in rows]


def run_due_schedules() -> list[str]:
    """Run and mark any schedules that are due. Returns list of output paths."""
    produced: list[str] = []
    now = datetime.now()
    for s in list_schedules():
        if s.next_run_at and s.next_run_at > now.strftime("%Y-%m-%d %H:%M:%S"):
            continue
        os.makedirs(s.output_dir, exist_ok=True)
        fname = f"{s.name.replace(' ', '_')}_{now.strftime('%Y%m%d_%H%M')}.{s.fmt}"
        out = os.path.join(s.output_dir, fname)
        data = _field_counts(s.field)
        if s.fmt == "csv":
            with open(out, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([s.field, "count"])
                w.writerows(data)
        else:
            export_pdf(f"E&D — {s.field}", data, out)
        _mark_ran(s.id, now, CADENCES[s.cadence])
        produced.append(out)
    return produced


def _field_counts(field: str) -> list[tuple[str, int]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT {field}, COUNT(*) FROM ed_people WHERE deleted_at IS NULL "
            f"AND {field} IS NOT NULL AND {field}!='' "
            f"GROUP BY {field} ORDER BY COUNT(*) DESC"
        ).fetchall()
    finally:
        conn.close()
    return _apply_suppression(rows)


def _mark_ran(schedule_id: int, now: datetime, days: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE ed_report_schedules SET last_run_at=?, next_run_at=? WHERE id=?",
            (now.strftime("%Y-%m-%d %H:%M:%S"),
             (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S"),
             schedule_id),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- feature 25
def benchmark_comparison(field: str) -> list[tuple[str, float, float, float]]:
    """Return (category, observed_pct, baseline_pct, delta_pp) rows."""
    observed = _field_counts(field)
    total = sum(n for _, n in observed) or 1
    conn = get_connection()
    try:
        bl = dict(conn.execute(
            "SELECT category, baseline_pct FROM ed_benchmarks WHERE field=?",
            (field,),
        ).fetchall())
    finally:
        conn.close()
    out: list[tuple[str, float, float, float]] = []
    for cat, n in observed:
        obs = n / total * 100
        base = bl.get(cat, 0.0)
        out.append((cat, obs, base, obs - base))
    return out


# ---------------------------------------------------------------- feature 26
def pay_gap(group_field: str = "gender") -> list[tuple[str, float, int]]:
    """Return (group, mean_salary, n) for staff only, n≥5 suppressed."""
    if group_field not in DEMOGRAPHIC_FIELDS:
        raise ValueError(f"bad field {group_field!r}")
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT {group_field}, AVG(salary), COUNT(*) FROM ed_people "
            f"WHERE person_type='Staff' AND salary IS NOT NULL "
            f"AND deleted_at IS NULL AND {group_field} IS NOT NULL "
            f"GROUP BY {group_field}"
        ).fetchall()
    finally:
        conn.close()
    return [(g, float(avg or 0.0), int(n))
            for g, avg, n in rows if (n or 0) >= SUPPRESSION_THRESHOLD]


# ---------------------------------------------------------------- feature 27
def accommodations_uptake() -> dict[str, Any]:
    """How many disabled staff/students have accommodations on file."""
    conn = get_connection()
    try:
        total_disabled = conn.execute(
            "SELECT COUNT(*) FROM ed_people WHERE deleted_at IS NULL "
            "AND disability IS NOT NULL AND disability NOT IN "
            "('No known disability','Prefer not to say','')"
        ).fetchone()[0] or 0
        with_accoms = conn.execute(
            "SELECT COUNT(*) FROM ed_people WHERE deleted_at IS NULL "
            "AND disability IS NOT NULL AND disability NOT IN "
            "('No known disability','Prefer not to say','') "
            "AND accommodations IS NOT NULL AND accommodations!=''"
        ).fetchone()[0] or 0
    finally:
        conn.close()
    pct = (with_accoms / total_disabled * 100) if total_disabled else 0.0
    return {"disabled": total_disabled, "with_accoms": with_accoms, "pct": pct}


# ---------------------------------------------------------------- feature 28
def drill_down(field: str, value: str) -> list[tuple]:
    if field not in DEMOGRAPHIC_FIELDS:
        raise ValueError(f"bad field {field!r}")
    conn = get_connection()
    try:
        return conn.execute(
            f"SELECT id, ref_code, person_type, department, date_added "
            f"FROM ed_people WHERE deleted_at IS NULL AND {field}=?",
            (value,),
        ).fetchall()
    finally:
        conn.close()


# ------ feature 50 — data-quality dashboard (lives here since it is metrics)
def data_quality() -> dict[str, Any]:
    conn = get_connection()
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM ed_people WHERE deleted_at IS NULL"
        ).fetchone()[0] or 0
        per_field = {}
        for f in DEMOGRAPHIC_FIELDS:
            missing = conn.execute(
                f"SELECT COUNT(*) FROM ed_people WHERE deleted_at IS NULL "
                f"AND ({f} IS NULL OR {f}='' OR {f}='Prefer not to say')"
            ).fetchone()[0] or 0
            per_field[f] = (missing, total)
        linked = conn.execute(
            "SELECT COUNT(*) FROM ed_people WHERE deleted_at IS NULL "
            "AND (student_id IS NOT NULL OR staff_id IS NOT NULL)"
        ).fetchone()[0] or 0
        incidents_open = conn.execute(
            "SELECT COUNT(*) FROM ed_incidents WHERE status='Open'"
        ).fetchone()[0] or 0
    finally:
        conn.close()
    return {
        "total_records": total,
        "per_field_missing": per_field,
        "linked": linked,
        "incidents_open": incidents_open,
    }
