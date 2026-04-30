"""Shared cross-domain services for the four academic GUIs.

Each function here is a pure data fetcher / side-effect helper used
by more than one of the Exam, Grade, Module, Course GUIs. Centralising
them avoids each GUI re-implementing the same query against a sibling
table — the bus in ``_event_bus.py`` already handles refresh
coordination, this module handles the actual aggregation.

Read paths return list[dict]; write paths return bool.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1) Conflict report shared across Module / Course / Exam
# ---------------------------------------------------------------------------

def _all_conflicts() -> list[dict[str, Any]]:
    """Run the canonical conflict detector and return its dict list."""
    try:
        from education_system.university_system.modules.domain.academics.services.module_scheduling.conflicts import (
            ConflictDetector,
        )
        return ConflictDetector(str(DEFAULT_DB_PATH)).detect_all_conflicts() or []
    except Exception as exc:
        logger.warning("conflict detector failed: %s", exc)
        return []


def find_conflicts_for_module(module_code: str) -> list[dict[str, Any]]:
    """Return only conflicts whose description mentions ``module_code``.

    Substring match is enough — every conflict description contains the
    affected module codes (see the writer in
    ``services.module_scheduling.conflicts``).
    """
    if not module_code:
        return []
    code = str(module_code).lower()
    return [c for c in _all_conflicts() if code in (c.get("description") or "").lower()]


def find_conflicts_for_course(course_code: str) -> list[dict[str, Any]]:
    """Return conflicts that touch any module belonging to ``course_code``.

    Looks up modules where ``modules.course = course_code`` and matches
    any conflict description that names them.
    """
    if not course_code:
        return []
    try:
        with get_connection() as conn:
            modules = [
                r[0] for r in conn.execute(
                    "SELECT module_code FROM modules WHERE course = ?",
                    (course_code,),
                ).fetchall()
            ] or [
                r[0] for r in conn.execute(
                    "SELECT module_code FROM modules WHERE course = ?",
                    (course_code.upper(),),
                ).fetchall()
            ]
    except Exception as exc:
        logger.warning("course module lookup failed: %s", exc)
        return []
    if not modules:
        return []
    needles = {m.lower() for m in modules if m}
    out = []
    for c in _all_conflicts():
        desc = (c.get("description") or "").lower()
        if any(n in desc for n in needles):
            out.append(c)
    return out


# ---------------------------------------------------------------------------
# 2) Prerequisite check at enrolment
# ---------------------------------------------------------------------------

def check_prerequisites(
    student_id: str | int,
    module_code: str,
    *,
    minimum_grade: str | None = None,
) -> dict[str, Any]:
    """Return ``{ok: bool, missing: [{code, name, min_grade}], reason}``.

    Reads ``course_prerequisites`` matched on ``module_code`` (the
    table also stores course-level rows; we filter to module-level by
    requiring ``module_code IS NOT NULL``). For each prereq, checks
    whether the student has a passing grade in either
    ``module_grades.final_grade`` or any ``student_grades`` row marked
    final.

    Returns ``ok=True`` (and no missing entries) when the table has no
    rules for the module, so this is safe to call in subsystems that
    haven't migrated their prereq data yet.
    """
    out: dict[str, Any] = {"ok": True, "missing": [], "reason": ""}
    if not student_id or not module_code:
        return out
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='course_prerequisites'"
            ).fetchone()
            if not tbl:
                return out
            # Module-level prereqs
            rules = conn.execute(
                """
                SELECT cp.prerequisite_module_code,
                       COALESCE(m.module_name, cp.prerequisite_module_code) AS pname,
                       cp.min_grade,
                       COALESCE(cp.is_required, 1) AS required
                FROM course_prerequisites cp
                LEFT JOIN modules m
                       ON m.module_code = cp.prerequisite_module_code
                WHERE cp.module_code = ?
                  AND cp.prerequisite_module_code IS NOT NULL
                """,
                (module_code,),
            ).fetchall()
            if not rules:
                return out

            # Build the student's "passed modules" set. Pass = any final
            # grade other than 'F' / NULL in either canonical table.
            passed: set[str] = set()
            try:
                for r in conn.execute(
                    "SELECT module_code, final_grade FROM module_grades WHERE student_id = ?",
                    (str(student_id),),
                ).fetchall():
                    if r["final_grade"] and r["final_grade"].strip().upper() != "F":
                        passed.add(r["module_code"])
            except sqlite3.OperationalError:
                pass
            try:
                for r in conn.execute(
                    "SELECT module_code, grade FROM student_grades "
                    "WHERE student_id = ? AND COALESCE(is_final, 1) = 1",
                    (str(student_id),),
                ).fetchall():
                    if r["grade"] and "F" not in r["grade"].upper().split("/")[0]:
                        passed.add(r["module_code"])
            except sqlite3.OperationalError:
                pass

            for rule in rules:
                code = rule["prerequisite_module_code"]
                required = bool(rule["required"])
                if code in passed:
                    continue
                if not required:
                    continue
                out["missing"].append({
                    "code": code,
                    "name": rule["pname"],
                    "min_grade": rule["min_grade"] or minimum_grade or "Pass",
                })
            if out["missing"]:
                names = ", ".join(m["code"] for m in out["missing"])
                out["ok"] = False
                out["reason"] = f"Missing required prerequisite(s): {names}"
    except Exception as exc:
        logger.warning(
            "check_prerequisites(%s, %s) failed: %s — defaulting to ok=True",
            student_id, module_code, exc,
        )
    return out


# ---------------------------------------------------------------------------
# 3) Consolidated instructor workload
# ---------------------------------------------------------------------------

def instructor_workload(instructor_id: int | None = None,
                        instructor_name: str | None = None) -> dict[str, Any]:
    """Return a per-instructor workload dict.

    ``{
        instructor: {id, name, email, department},
        teaching_slots: [{module, day, start, end, room}, ...],
        modules_taught: [module_code, ...],
        examiner_assignments: [{exam_id, module_code, role}, ...],
        recent_grades: int,                 # last 30d
        totals: {teaching_hours_per_week, slot_count, modules, exam_panels},
    }``
    """
    info = {"id": None, "name": "", "email": "", "department": ""}
    out = {
        "instructor": info,
        "teaching_slots": [],
        "modules_taught": [],
        "examiner_assignments": [],
        "recent_grades": 0,
        "totals": {"teaching_hours_per_week": 0.0, "slot_count": 0,
                   "modules": 0, "exam_panels": 0},
    }
    try:
        with get_connection() as conn:
            row = None
            if instructor_id is not None:
                row = conn.execute(
                    "SELECT id, first_name, last_name, email, department "
                    "FROM instructors WHERE id = ?", (instructor_id,),
                ).fetchone()
            elif instructor_name:
                row = conn.execute(
                    "SELECT id, first_name, last_name, email, department "
                    "FROM instructors "
                    "WHERE (first_name || ' ' || last_name) = ? "
                    "   OR email = ? LIMIT 1",
                    (instructor_name, instructor_name),
                ).fetchone()
            if not row:
                return out
            info["id"] = row["id"]
            info["name"] = f"{row['first_name']} {row['last_name']}".strip()
            info["email"] = row["email"] or ""
            info["department"] = row["department"] or ""

            # Teaching slots
            try:
                slots = conn.execute(
                    """
                    SELECT ms.module_code, ms.day_of_week, ms.start_time,
                           ms.end_time, COALESCE(r.building || '-' || r.room_number, '') AS room
                    FROM module_schedule ms
                    LEFT JOIN rooms r ON r.id = ms.room_id
                    WHERE ms.instructor_id = ?
                    ORDER BY ms.day_of_week, ms.start_time
                    """,
                    (info["id"],),
                ).fetchall()
                for s in slots:
                    out["teaching_slots"].append(dict(s))
            except sqlite3.OperationalError:
                pass

            out["modules_taught"] = sorted({s["module_code"] for s in out["teaching_slots"] if s["module_code"]})

            # Examiner panels
            try:
                rows = conn.execute(
                    """
                    SELECT eee.exam_id, e.module_code, eee.role
                    FROM exam_external_examiners eee
                    LEFT JOIN exams e ON e.id = eee.exam_id
                    WHERE eee.examiner_id = (
                        SELECT id FROM external_examiners WHERE id = ?
                    )
                    ORDER BY eee.id DESC
                    """,
                    (info["id"],),
                ).fetchall()
                for r in rows:
                    out["examiner_assignments"].append(dict(r))
            except sqlite3.OperationalError:
                pass

            # Recent grading activity
            try:
                cnt = conn.execute(
                    "SELECT COUNT(*) FROM student_grades "
                    "WHERE instructor = ? AND grade_date >= datetime('now','-30 days')",
                    (info["name"],),
                ).fetchone()
                out["recent_grades"] = int(cnt[0] or 0) if cnt else 0
            except sqlite3.OperationalError:
                pass

            # Totals
            hours = 0.0
            for s in out["teaching_slots"]:
                try:
                    sh, sm = (int(x) for x in (s["start_time"] or "00:00").split(":")[:2])
                    eh, em = (int(x) for x in (s["end_time"] or "00:00").split(":")[:2])
                    hours += max(0, (eh * 60 + em - sh * 60 - sm) / 60.0)
                except Exception:
                    pass
            out["totals"] = {
                "teaching_hours_per_week": round(hours, 2),
                "slot_count": len(out["teaching_slots"]),
                "modules": len(out["modules_taught"]),
                "exam_panels": len(out["examiner_assignments"]),
            }
    except Exception as exc:
        logger.warning("instructor_workload failed: %s", exc)
    return out


def list_instructors() -> list[dict[str, Any]]:
    """Return ``[{id, label}]`` for the workload dropdown."""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, first_name, last_name, email "
                "FROM instructors WHERE COALESCE(is_active, 1) = 1 "
                "ORDER BY last_name, first_name"
            ).fetchall()
            return [
                {"id": r["id"],
                 "label": f"{r['first_name']} {r['last_name']} ({r['email']})"}
                for r in rows
            ]
    except Exception as exc:
        logger.warning("list_instructors failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# 4) At-risk auto-sync (read-side)
# ---------------------------------------------------------------------------

def at_risk_students_unified(
    *,
    module_code: str | None = None,
    threshold: int = 30,
) -> list[dict[str, Any]]:
    """Read the unified at-risk list written by Grade Tracking.

    Joins ``early_warning_indicators`` (where ``flag_at_risk_student``
    writes) with ``students`` for display. When ``module_code`` is
    given, narrows to students enrolled in that module via
    ``student_modules``.
    """
    out = []
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='early_warning_indicators'"
            ).fetchone()
            if not tbl:
                return out
            params: list[Any] = [str(threshold)]
            sql = (
                "SELECT ewi.student_id, ewi.indicator_value AS risk_score, "
                "       ewi.severity, ewi.detected_at, ewi.notes, "
                "       s.first_name, s.last_name, s.course "
                "FROM early_warning_indicators ewi "
                "LEFT JOIN students s ON s.student_id = ewi.student_id "
                "WHERE ewi.indicator_type = 'grade_risk' "
                "  AND COALESCE(ewi.is_resolved, 0) = 0 "
                "  AND CAST(ewi.indicator_value AS INTEGER) >= ? "
            )
            if module_code:
                sql += (
                    "  AND ewi.student_id IN ("
                    "    SELECT student_id FROM student_modules WHERE module_code = ?"
                    "  ) "
                )
                params.append(module_code)
            sql += "ORDER BY CAST(ewi.indicator_value AS INTEGER) DESC LIMIT 100"
            for r in conn.execute(sql, tuple(params)).fetchall():
                d = dict(r)
                d["name"] = f"{d.get('first_name') or ''} {d.get('last_name') or ''}".strip() \
                            or d["student_id"]
                out.append(d)
    except Exception as exc:
        logger.warning("at_risk_students_unified failed: %s", exc)
    return out


# ---------------------------------------------------------------------------
# 5) Module timeline — assessments + exams + lecture slots
# ---------------------------------------------------------------------------

def module_timeline(module_code: str) -> list[dict[str, Any]]:
    """Combined timeline of every dated event tied to a module.

    Each row: ``{kind, date, label, detail}`` where ``kind`` is
    ``'lecture'``, ``'assessment'``, or ``'exam'``. Sorted ascending
    by date, then start time when available.
    """
    rows: list[dict[str, Any]] = []
    if not module_code:
        return rows
    try:
        with get_connection() as conn:
            tables = {
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            # Lecture slots — recurring weekly, no specific date, so
            # surface them as "Weekly: <day> <start>-<end>".
            if "module_schedule" in tables:
                for r in conn.execute(
                    "SELECT day_of_week, start_time, end_time, "
                    "       semester, year, status "
                    "FROM module_schedule WHERE module_code = ? "
                    "ORDER BY day_of_week, start_time",
                    (module_code,),
                ).fetchall():
                    rows.append({
                        "kind": "lecture",
                        "date": "",  # weekly recurring
                        "label": f"Weekly {r['day_of_week']} "
                                 f"{r['start_time']}–{r['end_time']}",
                        "detail": f"{r['semester'] or ''} {r['year'] or ''} "
                                  f"({r['status'] or 'published'})".strip(),
                    })
            # Assessments
            if "assessments" in tables:
                for r in conn.execute(
                    "SELECT assessment_name, assessment_type, due_date, "
                    "       max_points, status "
                    "FROM assessments WHERE module_code = ? "
                    "ORDER BY due_date",
                    (module_code,),
                ).fetchall():
                    rows.append({
                        "kind": "assessment",
                        "date": (r["due_date"] or "").split(" ")[0],
                        "label": r["assessment_name"] or "Assessment",
                        "detail": f"{r['assessment_type'] or 'assignment'} · "
                                  f"max {r['max_points'] or '—'} · "
                                  f"{r['status'] or 'open'}",
                    })
            # Exams
            if "exams" in tables:
                for r in conn.execute(
                    "SELECT id, date, start_time, end_time, room, students_enrolled "
                    "FROM exams WHERE module_code = ? "
                    "ORDER BY date, start_time",
                    (module_code,),
                ).fetchall():
                    rows.append({
                        "kind": "exam",
                        "date": r["date"] or "",
                        "label": f"Exam #{r['id']} — {r['room'] or 'no room'}",
                        "detail": f"{r['start_time']}–{r['end_time']} · "
                                  f"{r['students_enrolled'] or 0} enrolled",
                    })
    except Exception as exc:
        logger.warning("module_timeline(%s) failed: %s", module_code, exc)
    rows.sort(key=lambda x: (x.get("date") or "9999", x.get("label") or ""))
    return rows


__all__ = [
    "find_conflicts_for_module",
    "find_conflicts_for_course",
    "check_prerequisites",
    "instructor_workload",
    "list_instructors",
    "at_risk_students_unified",
    "module_timeline",
]
