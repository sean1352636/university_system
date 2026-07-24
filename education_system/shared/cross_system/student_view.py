"""The single student view — one learner's whole history, all five systems.

Given a canonical ``journey_id`` this builds a read-only, nested snapshot
of everything the platform knows about that person, in phase order::

    nursery → primary → secondary → sixth-form college → university

For each phase the learner actually reached it pulls the local record plus,
where the system keeps them, an attendance summary and recent results. The
cross-system links already exist (the ``student_journey`` slots and the
``journey_id`` FK stamped on each domain row); this is the first place that
*reads them all together*.

Everything here is defensive and read-only: a missing database, table or
column degrades to a partial view rather than an error, so the overview is
safe to call from an API handler or a dashboard.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from education_system.shared.auth.db import connect as _auth_connect
from education_system.shared.cross_system import identity_service, person
from education_system.shared.database.paths import (
    SYSTEM_DB_PATHS,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _connect(path) -> sqlite3.Connection | None:
    if not path or not Path(path).exists():
        return None
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _columns(conn, table) -> set[str]:
    try:
        return {r[1] for r in conn.execute(
            f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


def _table_exists(conn, table) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,)).fetchone()
    return row is not None


def _record(conn, table, pk_col, student_id, fields) -> dict:
    """Return the subset of ``fields`` actually present on a row."""
    present = [f for f in fields if f in _columns(conn, table)]
    if not present:
        return {}
    row = conn.execute(
        f"SELECT {', '.join(present)} FROM {table} WHERE {pk_col} = ?",
        (student_id,)).fetchone()
    return {k: row[k] for k in present} if row else {}


def _attendance_summary(conn, table, student_col, student_id,
                        mark_col) -> dict | None:
    """Count attendance rows grouped by their mark/status code."""
    if not _table_exists(conn, table):
        return None
    cols = _columns(conn, table)
    if student_col not in cols or mark_col not in cols:
        return None
    rows = conn.execute(
        f"SELECT {mark_col} AS mark, COUNT(*) AS n FROM {table} "
        f"WHERE {student_col} = ? GROUP BY {mark_col}",
        (student_id,)).fetchall()
    by_mark = {(r["mark"] or "?"): r["n"] for r in rows}
    total = sum(by_mark.values())
    if not total:
        return None
    return {"total": total, "by_mark": by_mark}


# ---------------------------------------------------------------------------
# Per-system extractors — each returns {record, attendance, results}
# ---------------------------------------------------------------------------

def _phase_nursery(conn, sid) -> dict:
    return {
        "record": _record(conn, "pupils", "pupil_id", sid, [
            "first_name", "last_name", "date_of_birth", "room",
            "key_person", "start_date", "status"]),
    }


def _phase_primary(conn, sid) -> dict:
    return {
        "record": _record(conn, "pupils", "pupil_id", sid, [
            "first_name", "last_name", "date_of_birth", "year_group",
            "class_name", "send_status", "email"]),
    }


def _phase_secondary(conn, sid) -> dict:
    out: dict = {
        "record": _record(conn, "pupils", "pupil_id", sid, [
            "first_name", "last_name", "date_of_birth", "year_group",
            "form_group", "send_status", "email"]),
        "attendance": _attendance_summary(
            conn, "attendance_records", "pupil_id", sid, "mark"),
    }
    if _table_exists(conn, "gradebook_entries"):
        rows = conn.execute(
            "SELECT subject_id, assessment_name, assessment_date, "
            "mark_pct, grade FROM gradebook_entries WHERE pupil_id = ? "
            "ORDER BY assessment_date DESC LIMIT 10", (sid,)).fetchall()
        out["results"] = [dict(r) for r in rows]
    return out


def _phase_college(conn, sid) -> dict:
    out: dict = {
        "record": _record(conn, "students", "student_id", sid, [
            "first_name", "middle_name", "last_name", "date_of_birth",
            "subject_1", "subject_2", "subject_3", "status", "email"]),
    }
    if _table_exists(conn, "mock_results") and _table_exists(conn, "mock_exams"):
        rows = conn.execute(
            "SELECT m.subject, m.title, m.date_sat, m.max_marks, "
            "r.marks, r.grade FROM mock_results r "
            "JOIN mock_exams m ON m.mock_id = r.mock_id "
            "WHERE r.student_id = ? ORDER BY m.date_sat DESC LIMIT 10",
            (sid,)).fetchall()
        out["results"] = [dict(r) for r in rows]
    return out


def _phase_university(conn, sid) -> dict:
    out: dict = {
        "record": _record(conn, "students", "student_id", sid, [
            "first_name", "last_name", "date_of_birth", "course",
            "status", "email", "enrollment_date"]),
        "attendance": _attendance_summary(
            conn, "attendance", "student_id", sid, "status"),
    }
    # University grade tables vary; surface whichever common one exists.
    for table, cols in (
        ("grades", "module_id, grade, score, graded_at"),
        ("enrollments", "module_id, status, grade"),
    ):
        if _table_exists(conn, table) and "student_id" in _columns(conn, table):
            present = [c.strip() for c in cols.split(",")
                       if c.strip() in _columns(conn, table)]
            if present:
                rows = conn.execute(
                    f"SELECT {', '.join(present)} FROM {table} "
                    "WHERE student_id = ? LIMIT 20", (sid,)).fetchall()
                out["results"] = [dict(r) for r in rows]
                break
    return out


_EXTRACTORS = {
    "nursery":    _phase_nursery,
    "primary":    _phase_primary,
    "secondary":     _phase_secondary,
    "sixth_form":    _phase_college,
    "university": _phase_university,
}


# ---------------------------------------------------------------------------
# Transitions timeline
# ---------------------------------------------------------------------------

def _transitions(journey_id, auth_db) -> list[dict]:
    conn = _auth_connect(auth_db)
    try:
        rows = conn.execute(
            "SELECT from_system, to_system, reason, occurred_at "
            "FROM student_journey_transitions WHERE journey_id = ? "
            "ORDER BY occurred_at, id", (journey_id,)).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_overview(journey_id: str, *, db_paths: dict | None = None,
                   auth_db: str | None = None) -> dict:
    """Aggregate a learner's whole cross-system history into one dict.

    ``db_paths`` / ``auth_db`` override the canonical registry locations
    (used by tests); production callers pass neither.
    """
    paths = db_paths if db_paths is not None else SYSTEM_DB_PATHS
    p = person.get(journey_id, db_path=auth_db)
    if p is None:
        return {"journey_id": journey_id, "found": False}

    phases = []
    for system in SYSTEM_ORDER:
        sid = p.local_id(system)
        if not sid:
            continue
        phase = {
            "system": system,
            "label": SYSTEM_LABELS.get(system, system.title()),
            "student_id": sid,
            "record": {},
        }
        conn = _connect(paths.get(system))
        if conn is not None:
            try:
                phase.update(_EXTRACTORS[system](conn, sid))
            except Exception:
                logger.debug("Phase extract failed for %s/%s", system,
                             sid, exc_info=True)
            finally:
                conn.close()
        phases.append(phase)

    return {
        "journey_id": journey_id,
        "found": True,
        "person": p.demographics() | {
            "full_name": p.full_name,
            "current_system": p.current_system,
            "status": p.status,
        },
        "phases": phases,
        "transitions": _transitions(journey_id, auth_db),
    }


def build_overview_for_student(system: str, student_id: str, *,
                               db_paths: dict | None = None,
                               auth_db: str | None = None) -> dict:
    """Convenience: resolve the journey from a local id, then aggregate."""
    row = identity_service.find_by_student(system, student_id,
                                           db_path=auth_db)
    if row is None:
        return {"found": False, "system": system, "student_id": student_id}
    return build_overview(row["journey_id"], db_paths=db_paths,
                          auth_db=auth_db)


def format_overview_text(overview: dict) -> str:
    """Render an overview as a compact plain-text summary (CLI / logs)."""
    if not overview.get("found"):
        return f"No journey found ({overview.get('journey_id', '?')})"
    p = overview["person"]
    lines = [
        f"{p.get('full_name', '?')}  (journey {overview['journey_id']})",
        f"  DOB {p.get('date_of_birth') or '—'}   "
        f"UPN {p.get('upn') or '—'}   NHS {p.get('nhs_number') or '—'}",
        f"  Currently: {p.get('current_system') or '—'} "
        f"({p.get('status') or '—'})",
        "  Phases:",
    ]
    for ph in overview["phases"]:
        rec = ph.get("record", {})
        bits = [f"{ph['label']} [{ph['student_id']}]"]
        if rec.get("year_group"):
            bits.append(f"Y{rec['year_group']}")
        if rec.get("course"):
            bits.append(str(rec["course"]))
        if rec.get("status"):
            bits.append(str(rec["status"]))
        att = ph.get("attendance")
        if att:
            bits.append(f"attendance n={att['total']}")
        res = ph.get("results")
        if res:
            bits.append(f"{len(res)} result(s)")
        lines.append("    - " + "  ".join(bits))
    if overview["transitions"]:
        lines.append("  Transitions:")
        for t in overview["transitions"]:
            lines.append(
                f"    {t.get('occurred_at', '?')}  "
                f"{t.get('from_system') or '—'} → {t.get('to_system')}")
    return "\n".join(lines)


__all__ = [
    "build_overview",
    "build_overview_for_student",
    "format_overview_text",
]
