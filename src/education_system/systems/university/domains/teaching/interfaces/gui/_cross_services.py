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
from typing import Any, Optional

from education_system.systems.university.infrastructure.database.db import (
    sqlite3,
    get_connection,
    reuse_connection,
)
from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1) Conflict report shared across Module / Course / Exam
# ---------------------------------------------------------------------------

def _all_conflicts() -> list[dict[str, Any]]:
    """Return the current list of unresolved scheduling conflicts.

    The canonical detector is the ``ConflictsMixin`` in
    ``services.module_scheduling.conflicts`` — but it's a mixin (needs
    ``self.db_path``), not a standalone class. We compose a tiny host
    on the fly to invoke it. On any failure we fall back to reading
    the persisted ``schedule_conflicts`` table, which is what the
    detector writes to anyway, so callers still see something useful
    even when the detector can't run (e.g. missing tables).
    """
    try:
        from education_system.systems.university.domains.teaching.domain.module_scheduling.conflicts import (
            ConflictsMixin,
        )

        class _DetectorHost(ConflictsMixin):
            def __init__(self, db_path: str) -> None:
                self.db_path = db_path

        # The detector checks each student's timetable separately and opens a
        # connection per check — ~25 per pass, at ~97ms each, which was most of
        # a single pass's cost. Share one connection for the pass; the
        # detector's own get_connection() calls pick it up unchanged.
        #
        # db_path and row_factory must match what the detector asks for
        # (`get_connection(self.db_path, row_factory=False)`) — reuse is
        # deliberately not granted across a differing row_factory, since that
        # would hand back rows of the wrong type.
        with reuse_connection(UNIVERSITY_DEFAULT_DB_PATH, row_factory=False):
            return _DetectorHost(str(UNIVERSITY_DEFAULT_DB_PATH)).detect_all_conflicts() or []
    except Exception as exc:
        logger.debug("live conflict detection failed (%s); reading table",
                     exc)

    # Fallback: read whatever the detector last persisted.
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='schedule_conflicts'"
            ).fetchone()
            if not tbl:
                return []
            rows = conn.execute(
                "SELECT conflict_type AS type, description, "
                "       'medium' AS severity "
                "FROM schedule_conflicts "
                "WHERE COALESCE(resolved, 0) = 0 "
                "ORDER BY detected_date DESC"
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as exc:
        logger.warning("conflict table fallback failed: %s", exc)
        return []


def find_conflicts_for_courses(
    course_codes: "list[str] | tuple[str, ...] | set[str]",
) -> dict[str, list[dict[str, Any]]]:
    """Conflicts per course, computed with **one** detection pass.

    ``find_conflicts_for_course`` runs the full scheduling-conflict detector
    over the whole database on every call. Calling it once per row — which the
    Course Management list did for each of its courses — re-ran that entire
    detection for every course, and each pass opened its own pile of database
    connections. That was ~50s to open the Course Management window against a
    modest dataset.

    This does the work once: one detection pass, one module lookup for every
    course, then pure in-memory matching. Same substring-matching semantics as
    ``find_conflicts_for_course`` (every conflict description names the modules
    it affects), so results are identical.

    Returns a dict keyed by the course codes passed in; courses with no
    conflicts map to an empty list.
    """
    codes = [str(c) for c in course_codes if c]
    result: dict[str, list[dict[str, Any]]] = {c: [] for c in codes}
    if not codes:
        return result

    # One lookup of every course's modules, rather than two queries per course.
    # Matched case-insensitively so the original's ``course_code.upper()``
    # retry is covered by the same pass.
    modules_by_course: dict[str, set[str]] = {c: set() for c in codes}
    wanted = {c.upper(): c for c in codes}
    try:
        with get_connection() as conn:
            placeholders = ",".join("?" for _ in codes)
            rows = conn.execute(
                "SELECT course, module_code FROM modules "
                f"WHERE UPPER(course) IN ({placeholders})",  # nosec B608 - placeholders only
                [c.upper() for c in codes],
            ).fetchall()
        for course, module_code in rows:
            original = wanted.get(str(course).upper())
            if original and module_code:
                modules_by_course[original].add(str(module_code).lower())
    except Exception as exc:
        logger.warning("batch course module lookup failed: %s", exc)
        return result

    conflicts = _all_conflicts()
    if not conflicts:
        return result

    descriptions = [((c.get("description") or "").lower(), c) for c in conflicts]
    for code in codes:
        needles = modules_by_course.get(code) or set()
        if not needles:
            continue
        result[code] = [c for desc, c in descriptions if any(n in desc for n in needles)]
    return result


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
                    WHERE eee.examiner_id IN (
                        SELECT examiner_id FROM external_examiners
                         WHERE LOWER(email) = LOWER(?)
                    )
                    ORDER BY eee.id DESC
                    """,
                    (info["email"],),
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
                    logger.debug("Suppressed exception", exc_info=True)
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


# ---------------------------------------------------------------------------
# 6) Weighted module grade — single source of truth
# ---------------------------------------------------------------------------

def compute_module_grade(
    student_id: str | int,
    module_code: str,
) -> dict[str, Any]:
    """Return ``{percentage, letter, components, missing}`` for one module.

    Weighting comes from ``assessments.weight`` (per ``module_code``).
    Marks are pulled, in order of preference, from:
      1. ``student_grades`` rows joined on assessment_id / module_code,
      2. ``assignment_submissions.grade`` joined via ``assignments`` for
         any assessment whose name matches an assignment title in the
         same module (so the assignment GUI's grades feed in).

    When no assessment rows exist for the module, falls back to a
    simple unweighted mean over ``student_grades`` for that student
    and module — keeps callers useful on partially-migrated data.
    """
    out: dict[str, Any] = {
        "percentage": None,
        "letter": "",
        "components": [],   # [{name, weight, score, source}]
        "missing": [],      # assessments with no recorded mark
    }
    if not student_id or not module_code:
        return out
    sid = str(student_id)

    try:
        with get_connection() as conn:
            tables = {
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            assessments: list[dict[str, Any]] = []
            if "assessments" in tables:
                for r in conn.execute(
                    "SELECT assessment_id, assessment_name, weight, max_points "
                    "FROM assessments WHERE module_code = ?",
                    (module_code,),
                ).fetchall():
                    assessments.append(dict(r))

            # Unweighted fallback: no assessment rows for this module.
            if not assessments:
                rows = []
                if "student_grades" in tables:
                    try:
                        rows = conn.execute(
                            "SELECT grade FROM student_grades "
                            "WHERE student_id = ? AND module_code = ?",
                            (sid, module_code),
                        ).fetchall()
                    except sqlite3.OperationalError:
                        rows = []
                pcts = []
                for r in rows:
                    g = (r[0] or "").strip()
                    try:
                        pcts.append(float(g.rstrip("%")))
                    except ValueError:
                        continue
                if pcts:
                    out["percentage"] = round(sum(pcts) / len(pcts), 2)
                out["letter"] = _letter(out["percentage"])
                return out

            total_weight = 0.0
            weighted_sum = 0.0
            for a in assessments:
                aid = a.get("assessment_id")
                name = a.get("assessment_name") or f"#{aid}"
                weight = float(a.get("weight") or 0)
                max_points = float(a.get("max_points") or 100)
                score_pct: float | None = None
                source = ""

                # 1) student_grades joined by assessment_id
                if "student_grades" in tables and aid is not None:
                    try:
                        row = conn.execute(
                            "SELECT grade FROM student_grades "
                            "WHERE student_id = ? "
                            "AND (assessment_name, module_code) = "
                            "(SELECT assessment_name, module_code FROM assessments WHERE assessment_id = ?) "
                            "ORDER BY rowid DESC LIMIT 1",
                            (sid, aid),
                        ).fetchone()
                    except sqlite3.OperationalError:
                        row = None
                    if row and row[0]:
                        try:
                            score_pct = float(str(row[0]).rstrip("%"))
                            source = "student_grades"
                        except ValueError:
                            pass

                # 2) assignment_submissions matched by title in same module
                if score_pct is None and "assignment_submissions" in tables:
                    try:
                        row = conn.execute(
                            "SELECT sub.grade "
                            "FROM assignment_submissions sub "
                            "JOIN assignments a ON sub.assignment_id = a.id "
                            "WHERE sub.student_id = ? "
                            "  AND a.module_code = ? "
                            "  AND a.title = ? "
                            "ORDER BY sub.submission_date DESC LIMIT 1",
                            (sid, module_code, name),
                        ).fetchone()
                    except sqlite3.OperationalError:
                        row = None
                    if row and row[0] is not None:
                        try:
                            # assignment_submissions.grade is already a percentage
                            score_pct = float(row[0])
                            source = "assignment_submissions"
                        except (TypeError, ValueError):
                            pass

                comp = {
                    "name": name,
                    "weight": weight,
                    "max_points": max_points,
                    "score": score_pct,
                    "source": source,
                }
                out["components"].append(comp)
                if score_pct is None:
                    out["missing"].append(name)
                    continue
                if weight > 0:
                    total_weight += weight
                    weighted_sum += score_pct * weight

            if total_weight > 0:
                out["percentage"] = round(weighted_sum / total_weight, 2)
            out["letter"] = _letter(out["percentage"])
    except Exception as exc:
        logger.warning(
            "compute_module_grade(%s, %s) failed: %s",
            student_id, module_code, exc,
        )
    return out


# ---------------------------------------------------------------------------
# 7) Free-room finder — single algorithm, all four schedulers
# ---------------------------------------------------------------------------

def find_free_rooms(
    *,
    day_of_week: str | None = None,
    on_date: str | None = None,
    start_time: str,
    end_time: str,
    min_capacity: int | None = None,
    exclude_schedule_id: int | None = None,
    exclude_exam_id: int | None = None,
) -> list[dict[str, Any]]:
    """Return rooms free for the given window.

    A room is "free" iff:
      * No row in ``module_schedule`` overlaps the window on the same
        weekday (recurring lecture slots).
      * No row in ``exams`` overlaps the window on ``on_date`` (one-off
        exam bookings).
      * Optional ``min_capacity`` floor on ``rooms.capacity``.

    Either ``day_of_week`` *or* ``on_date`` must be supplied:
      * ``day_of_week`` for weekly recurring use (lectures).
      * ``on_date`` for one-off use (exams). If a date is given, the
        weekday is derived for the recurring-slot check too.

    Returns ``[{id, name, building, capacity, has_projector,
    has_computers}]``. Empty list on failure — callers fall back to
    showing all rooms.
    """
    if not start_time or not end_time:
        return []
    if not day_of_week and not on_date:
        return []

    derived_day = day_of_week
    if not derived_day and on_date:
        try:
            from datetime import datetime as _dt
            derived_day = _dt.strptime(on_date[:10], "%Y-%m-%d").strftime("%A")
        except Exception:
            derived_day = None

    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            params: list[Any] = []
            # rooms schema varies — newer rows use ``room_name``,
            # older ones only have ``room_number``. Equipment is a free-
            # text column rather than booleans, so we surface its
            # presence as substring flags for back-compat with callers.
            sql = (
                "SELECT id, "
                "       COALESCE(room_name, room_number) AS name, "
                "       COALESCE(building, '') AS building, "
                "       COALESCE(capacity, 0) AS capacity, "
                "       CASE WHEN LOWER(COALESCE(equipment, '')) "
                "            LIKE '%projector%' THEN 1 ELSE 0 END "
                "         AS has_projector, "
                "       CASE WHEN LOWER(COALESCE(equipment, '')) "
                "            LIKE '%computer%' THEN 1 ELSE 0 END "
                "         AS has_computers "
                "FROM rooms WHERE COALESCE(is_active, 1) = 1 "
            )
            if min_capacity is not None:
                sql += "AND COALESCE(capacity, 0) >= ? "
                params.append(int(min_capacity))
            sql += "ORDER BY capacity DESC"
            rooms = conn.execute(sql, tuple(params)).fetchall()

            for r in rooms:
                room_id = r["id"]

                # Lecture slot conflict (recurring weekday).
                lecture_conflict = False
                if derived_day:
                    q = (
                        "SELECT 1 FROM module_schedule "
                        "WHERE room_id = ? AND day_of_week = ? "
                        "  AND start_time < ? AND end_time > ? "
                    )
                    qp: list[Any] = [room_id, derived_day,
                                     end_time, start_time]
                    if exclude_schedule_id is not None:
                        q += "AND id != ? "
                        qp.append(exclude_schedule_id)
                    q += "LIMIT 1"
                    if conn.execute(q, tuple(qp)).fetchone():
                        lecture_conflict = True
                if lecture_conflict:
                    continue

                # Exam booking conflict (specific date).
                exam_conflict = False
                if on_date:
                    eq = (
                        "SELECT 1 FROM exams "
                        "WHERE date = ? AND room = ? "
                        "  AND start_time < ? AND end_time > ? "
                    )
                    ep: list[Any] = [on_date[:10], r["name"],
                                     end_time, start_time]
                    if exclude_exam_id is not None:
                        eq += "AND id != ? "
                        ep.append(exclude_exam_id)
                    eq += "LIMIT 1"
                    try:
                        if conn.execute(eq, tuple(ep)).fetchone():
                            exam_conflict = True
                    except sqlite3.OperationalError:
                        pass
                if exam_conflict:
                    continue

                out.append(dict(r))
    except Exception as exc:
        logger.warning("find_free_rooms failed: %s", exc)
        return []
    return out


# ---------------------------------------------------------------------------
# 8) Calendar period authority — single source of truth for term windows
# ---------------------------------------------------------------------------

# Recognised period kinds. The calendar stores them as
# ``academic_calendar_events.event_type`` strings (case-insensitive).
PERIOD_KINDS = (
    "term", "reading_week", "exam_window",
    "submission_window", "holiday",
)


def _current_academic_term(target: str) -> dict[str, Any] | None:
    """The ``academic_terms`` row covering ``target``, shaped like a period.

    Returns the same keys ``current_period`` yields for a calendar event
    (``id``/``name``/``date_start``/``date_end``/``event_type``) plus the
    term's own ``term_type``, ``academic_year`` and ``status``, so callers
    that only wanted a date span keep working unchanged.

    Cancelled and archived terms are ignored — they are history, not "now".
    """
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='academic_terms'"
            ).fetchone()
            if not tbl:
                return None
            row = conn.execute(
                "SELECT id, name, term_type, academic_year, start_date, "
                "       end_date, status "
                "  FROM academic_terms "
                " WHERE start_date IS NOT NULL AND end_date IS NOT NULL "
                "   AND start_date <= ? AND end_date >= ? "
                "   AND LOWER(COALESCE(status, '')) "
                "       NOT IN ('cancelled', 'archived') "
                " ORDER BY start_date DESC LIMIT 1",
                (target, target),
            ).fetchone()
            if not row:
                return None
            keys = ("id", "name", "term_type", "academic_year",
                    "start_date", "end_date", "status")
            term = dict(zip(keys, row))
            # Period-shaped aliases, so existing callers need no changes.
            term["date_start"] = term["start_date"]
            term["date_end"] = term["end_date"]
            term["date"] = None
            term["event_type"] = "term"
            return term
    except Exception as exc:
        logger.warning("could not read academic_terms: %s", exc)
        return None


def current_period(kind: str, *, on_date: str | None = None) -> dict[str, Any] | None:
    """Return the active period of ``kind`` covering ``on_date`` (default today).

    Reads ``academic_calendar_events`` rows whose ``event_type``
    matches ``kind`` (case-insensitive) and whose date range covers
    the target date. The Calendar GUI is the canonical writer; every
    other GUI calls this instead of hardcoding semester boundaries.

    Returns ``None`` if no matching period exists or the calendar
    table isn't present.
    """
    from datetime import date as _date
    target = (on_date or _date.today().isoformat())[:10]

    # Terms are not calendar events. The Calendar GUI keeps them in its own
    # ``academic_terms`` table (Calendar → Terms), so a term defined there was
    # invisible to every GUI asking "which term is it?" — Module Management
    # showed "No active term / period set" while the calendar plainly listed
    # the term. Ask the terms table first and fall back to a calendar event of
    # type 'term' for anyone still recording them that way.
    if (kind or "").lower() == "term":
        term = _current_academic_term(target)
        if term is not None:
            return term

    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='academic_calendar_events'"
            ).fetchone()
            if not tbl:
                return None
            row = conn.execute(
                "SELECT id, name, date, date_start, date_end, event_type "
                "FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') "
                "WHERE LOWER(event_type) = LOWER(?) "
                "  AND ( "
                "    (date_start IS NOT NULL AND date_end IS NOT NULL "
                "     AND date_start <= ? AND date_end >= ?) "
                "    OR (date IS NOT NULL AND date = ?) "
                "  ) "
                "ORDER BY COALESCE(date_start, date) DESC LIMIT 1",
                (kind, target, target, target),
            ).fetchone()
            return dict(row) if row else None
    except Exception as exc:
        logger.warning("current_period(%s) failed: %s", kind, exc)
        return None


def holiday_for(check_date: str) -> Optional[dict]:
    """The holiday covering ``check_date``, or ``None``.

    Returns ``{"name", "start", "end", "source"}`` so callers can tell
    the user *which* holiday blocked them and over what range — "falls
    on a holiday" on its own leaves them with nowhere to go.

    Checks the Calendar's ``academic_calendar_events`` rows
    (event_type='holiday') and the legacy ``holidays`` table.
    """
    if not check_date:
        return None
    target = str(check_date)[:10]
    try:
        with get_connection() as conn:
            tables = {
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "academic_calendar_events" in tables:
                # date_start/date_end alias start_datetime/end_datetime,
                # which carry a time component. Comparing those against a
                # bare 'YYYY-MM-DD' fails for the start bound, because
                # '2026-09-09 09:00' > '2026-09-09' as a string. Compare
                # on the date portion only.
                row = conn.execute(
                    "SELECT name, date, date_start, date_end FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') "
                    "WHERE LOWER(event_type) = 'holiday' AND ( "
                    "  (date_start IS NOT NULL AND date_end IS NOT NULL "
                    "   AND substr(date_start, 1, 10) <= ? "
                    "   AND substr(date_end, 1, 10) >= ?) "
                    "  OR (substr(date, 1, 10) = ?) "
                    ") LIMIT 1",
                    (target, target, target),
                ).fetchone()
                if row:
                    start = (row[2] or row[1] or target)[:10]
                    end = (row[3] or row[1] or target)[:10]
                    return {"name": row[0] or "Holiday", "start": start,
                            "end": end, "source": "academic calendar"}
            if "holidays" in tables:
                row = conn.execute(
                    "SELECT holiday_name, start_date, end_date FROM holidays "
                    "WHERE substr(start_date, 1, 10) <= ? "
                    "  AND substr(end_date, 1, 10) >= ? LIMIT 1",
                    (target, target),
                ).fetchone()
                if row:
                    return {"name": row[0] or "Holiday",
                            "start": str(row[1])[:10],
                            "end": str(row[2])[:10],
                            "source": "holidays table"}
    except Exception as exc:
        logger.warning("holiday_for(%s) failed: %s", check_date, exc)
    return None


def describe_holiday(check_date: str) -> str:
    """A human phrase for the holiday on ``check_date``, or ``""``."""
    holiday = holiday_for(check_date)
    if not holiday:
        return ""
    if holiday["start"] == holiday["end"]:
        return f"{holiday['name']} ({holiday['start']})"
    return (f"{holiday['name']} "
            f"({holiday['start']} to {holiday['end']})")


def is_holiday(check_date: str) -> bool:
    """``True`` if ``check_date`` falls inside any holiday period."""
    return holiday_for(check_date) is not None


def _letter(pct: float | None) -> str:
    if pct is None:
        return ""
    if pct >= 70: return "A"
    if pct >= 60: return "B"
    if pct >= 50: return "C"
    if pct >= 40: return "D"
    return "F"


__all__ = [
    "find_conflicts_for_module",
    "find_conflicts_for_course",
    "check_prerequisites",
    "instructor_workload",
    "list_instructors",
    "at_risk_students_unified",
    "module_timeline",
    "compute_module_grade",
    "find_free_rooms",
    "current_period",
    "is_holiday",
    "PERIOD_KINDS",
]
