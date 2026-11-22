"""Exam results through the marking rules.

Exam Management used to write results straight into ``student_grades`` and
``student_modules``: one exam set the whole module to completed/failed (with
lower-case statuses nothing else recognises), the result never reached the
module calculation, students saw it immediately, and nothing stopped it
overwriting a module an exam board had ratified.

Now each sitting is linked to an ``assessments`` row and its marks go into
``grades`` through :mod:`exam_marking` — so they count in the combined module
result (:mod:`module_results`), are held until released, can be moderated
and marked anonymously, and respect board locks. Transcripts get the mark
when it is released.

Functions take an open connection and do not commit.
"""

from __future__ import annotations

import json
from datetime import datetime

from education_system.systems.university.application.exams import marking as exam_marking
from education_system.systems.university.infrastructure.database.db import sqlite3

ABSENCE_CODES = exam_marking.ABSENCE_CODES


class ExamResultsError(ValueError):
    """A results rule refused the action; the message is safe to show."""


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _columns(conn, table):
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}


def _exam(conn, exam_id) -> dict:
    cur = conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,))
    row = cur.fetchone()
    if row is None:
        raise ExamResultsError(f"Exam {exam_id} not found.")
    return dict(zip([d[0] for d in cur.description], row))


def exam_title(exam: dict) -> str:
    """The assessment name for a sitting — the same "<module name> Exam" the
    exam→assignment sync uses, so the two are recognised as one piece of work."""
    if exam.get("exam_name"):
        return exam["exam_name"]
    name = exam.get("module_name") or exam["module_code"]
    if "(Resit)" in name:
        return name
    return f"{name} Exam"


# ── the exam ↔ assessment link ──────────────────────────────────────────


def _find_assessment(conn, exam, cols):
    if "exam_id" in cols:
        row = conn.execute("SELECT assessment_id FROM assessments WHERE exam_id = ?",
                           (exam["id"],)).fetchone()
        if row:
            return row[0]
    row = conn.execute(
        "SELECT assessment_id FROM assessments WHERE module_code = ? AND assessment_name = ? "
        "AND reassessment_of IS NULL ORDER BY assessment_id LIMIT 1",
        (exam["module_code"], exam_title(exam))).fetchone()
    return row[0] if row else None


def assessment_for_exam(conn, exam_id, create=True):
    """The assessment a sitting's marks belong to, creating it if needed.

    A new one has weight 0 — the module's weightings decide what it counts
    for (the Module Results screen flags a module whose weights are unset).
    """
    exam = _exam(conn, exam_id)
    if exam.get("assessment_id") and conn.execute(
            "SELECT 1 FROM assessments WHERE assessment_id = ?", (exam["assessment_id"],)).fetchone():
        return exam["assessment_id"]
    cols = _columns(conn, "assessments")
    aid = _find_assessment(conn, exam, cols)
    if aid is None:
        if not create:
            return None
        values = {"assessment_name": exam_title(exam), "assessment_type": "exam",
                  "module_code": exam["module_code"], "max_points": 100, "weight": 0,
                  "due_date": exam.get("date"), "description": "Scheduled exam sitting"}
        if "exam_id" in cols:
            values["exam_id"] = exam["id"]
        names = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        aid = conn.execute(f"INSERT INTO assessments ({names}) VALUES ({marks})",  # nosec B608 - fixed keys
                           tuple(values.values())).lastrowid
    conn.execute("UPDATE exams SET assessment_id = ? WHERE id = ?", (aid, exam_id))
    if "exam_id" in cols:
        conn.execute("UPDATE assessments SET exam_id = ? WHERE assessment_id = ? AND exam_id IS NULL",
                     (exam_id, aid))
    return aid


def roster(conn, exam) -> list[str]:
    """Students sitting an exam: its explicit list, else the module's enrolments."""
    raw = exam.get("enrolled_student_ids")
    try:
        ids = [str(s) for s in (json.loads(raw) if isinstance(raw, str) else raw or [])]
    except (TypeError, ValueError):
        ids = []
    if ids:
        return ids
    return [r[0] for r in conn.execute(
        "SELECT student_id FROM student_modules WHERE module_code = ? "
        "AND LOWER(COALESCE(status, 'enrolled')) = 'enrolled'", (exam["module_code"],))]


# ── results ─────────────────────────────────────────────────────────────


def existing_results(conn, exam_id) -> dict:
    """{student_id: percentage or absence code} already recorded for a sitting."""
    aid = assessment_for_exam(conn, exam_id, create=False)
    if aid is None:
        return {}
    a = exam_marking.get_settings(conn, aid)
    out = {}
    for sid, score, code in conn.execute(
            "SELECT student_id, score, result_code FROM grades WHERE assessment_id = ? "
            "ORDER BY grade_id", (aid,)):
        if code:
            out[str(sid)] = code
        elif score is not None:
            out[str(sid)] = round(float(score) / float(a["max_points"] or 100) * 100, 2)
    return out


def _normalise(value):
    if isinstance(value, str) and value.strip().upper() in ABSENCE_CODES:
        return value.strip().upper()
    pct = float(value)
    if not 0 <= pct <= 100:
        raise ExamResultsError(f"{value} is not a percentage from 0 to 100.")
    return round(pct, 2)


def changed_students(conn, exam_id, results) -> list[str]:
    """Students whose new result differs from one already recorded (these need a reason)."""
    existing = existing_results(conn, exam_id)
    changed = []
    for sid, value in results.items():
        try:
            new = _normalise(value)
        except (ValueError, TypeError):
            continue
        old = existing.get(str(sid))
        if old is not None and str(old) != str(new):
            changed.append(str(sid))
    return changed


def _write_score(conn, aid, max_points, sid, pct, graded_by):
    score = round(pct * float(max_points or 100) / 100, 2)
    row = conn.execute("SELECT grade_id FROM grades WHERE assessment_id = ? AND student_id = ? "
                       "ORDER BY grade_id DESC LIMIT 1", (aid, sid)).fetchone()
    if row:
        conn.execute("UPDATE grades SET score = ?, result_code = NULL, letter_grade = ?, "
                     "submission_date = ?, graded_by = ? WHERE grade_id = ?",
                     (score, None, _now()[:10], graded_by, row[0]))
        return row[0]
    return conn.execute(
        "INSERT INTO grades (student_id, assessment_id, score, submission_date, graded_by) "
        "VALUES (?, ?, ?, ?, ?)", (sid, aid, score, _now()[:10], graded_by)).lastrowid


def record_results(conn, exam_id, results, graded_by=None, reason=None) -> dict:
    """Record a sitting's results: a percentage or ABS/ABS-MC per student.

    Changing an existing result needs ``reason``. A student whose module
    result an exam board has ratified is refused (the lock trigger) and
    reported, without stopping the others.
    """
    aid = assessment_for_exam(conn, exam_id)
    a = exam_marking.get_settings(conn, aid)
    changed = set(changed_students(conn, exam_id, results))
    if changed and not (reason or "").strip():
        raise ExamResultsError(f"{len(changed)} recorded result(s) would change; give a reason.")
    existing = existing_results(conn, exam_id)
    written, errors = 0, []
    for sid, value in results.items():
        sid = str(sid)
        try:
            new = _normalise(value)
            conn.execute("SAVEPOINT exam_result")
            if sid in changed:
                exam_marking.log_change(conn, source="grades", record_id=None, student_id=sid,
                                        module_code=a["module_code"], old_value=existing.get(sid),
                                        new_value=new, reason=reason, changed_by=graded_by)
            if isinstance(new, str):
                exam_marking.record_absence(conn, aid, sid, new, graded_by, reason=reason)
            else:
                grade_id = _write_score(conn, aid, a["max_points"], sid, new, graded_by)
                exam_marking.after_mark(conn, grade_id, graded_by)
            conn.execute("RELEASE SAVEPOINT exam_result")
            written += 1
        except (sqlite3.Error, ValueError, TypeError) as exc:
            conn.execute("ROLLBACK TO SAVEPOINT exam_result")
            conn.execute("RELEASE SAVEPOINT exam_result")
            errors.append((sid, str(exc)))
    return {"written": written, "errors": errors, "assessment_id": aid,
            "released": bool(a.get("marks_released_at"))}


def _approved_missed_exam(conn, exam_id, student_id) -> bool:
    if not _columns(conn, "absence_requests"):
        return False
    return conn.execute(
        "SELECT 1 FROM absence_requests WHERE exam_id = ? AND student_id = ? "
        "AND LOWER(COALESCE(status, '')) = 'approved'", (exam_id, str(student_id))).fetchone() is not None


def absentees(conn, exam_id) -> list[dict]:
    """Students on the roster with no result after the exam: ABS, or ABS-MC
    where a missed-exam request was approved."""
    exam = _exam(conn, exam_id)
    if (exam.get("date") or "") > _now()[:10]:
        return []
    recorded = existing_results(conn, exam_id)
    out = []
    for sid in roster(conn, exam):
        if sid in recorded:
            continue
        code = "ABS-MC" if _approved_missed_exam(conn, exam_id, sid) else "ABS"
        out.append({"student_id": sid, "code": code})
    return out


def record_absentees(conn, exam_id, recorded_by=None) -> int:
    pending = absentees(conn, exam_id)
    if not pending:
        return 0
    result = record_results(conn, exam_id, {p["student_id"]: p["code"] for p in pending}, recorded_by)
    return result["written"]


# ── resits for scheduled exams ──────────────────────────────────────────


def link_resit(conn, original_exam_id, resit_exam_id, student_id, attempt_type="deferral",
               mc_claim_id=None, created_by=None) -> int:
    """Connect a resit sitting (created by the deferred-exam screen) to the
    resit rules: the student gets a resit record (uncapped deferral or capped
    referral) and the resit sitting's marks replace the original. A deferred
    student with no mark on the original gets ABS-MC there."""
    original_aid = assessment_for_exam(conn, original_exam_id)
    resit = _exam(conn, resit_exam_id)
    sid = str(student_id)
    if resit.get("assessment_id"):
        resit_aid = resit["assessment_id"]
        conn.execute(
            "INSERT OR IGNORE INTO exam_reassessments (original_assessment_id, reassessment_assessment_id, "
            "student_id, attempt_type, mark_cap_pct, mc_claim_id, created_at, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (original_aid, resit_aid, sid, attempt_type,
             exam_marking.PASS_MARK if attempt_type == "referral" else None, mc_claim_id, _now(), created_by))
    else:
        resit_aid = exam_marking.create_resit(
            conn, original_aid, [{"student_id": sid, "attempt_type": attempt_type, "mc_claim_id": mc_claim_id}],
            resit.get("date"), created_by)
        conn.execute("UPDATE exams SET assessment_id = ? WHERE id = ?", (resit_aid, resit_exam_id))
    if attempt_type == "deferral" and sid not in existing_results(conn, original_exam_id):
        exam_marking.record_absence(conn, original_aid, sid, "ABS-MC", created_by,
                                    reason="Approved missed-exam request; deferred sitting")
    return resit_aid


# ── online exams ────────────────────────────────────────────────────────


def assessment_for_portal_exam(conn, portal_exam_id, scheduler_exam_id=None) -> int | None:
    """The assessment an online exam's results belong to: its scheduled
    sitting's, when it mirrors one, otherwise its own."""
    row = conn.execute("SELECT title, module_code, assessment_id, end_time FROM exam_portal_exams "
                       "WHERE id = ?", (portal_exam_id,)).fetchone()
    if row is None or not row[1]:
        return None
    if row[2] and conn.execute("SELECT 1 FROM assessments WHERE assessment_id = ?", (row[2],)).fetchone():
        return row[2]
    if scheduler_exam_id:
        aid = assessment_for_exam(conn, scheduler_exam_id)
    else:
        name = f"{row[0]} (online #{portal_exam_id})"
        found = conn.execute("SELECT assessment_id FROM assessments WHERE module_code = ? "
                             "AND assessment_name = ?", (row[1], name)).fetchone()
        aid = found[0] if found else conn.execute(
            "INSERT INTO assessments (assessment_name, assessment_type, module_code, max_points, weight, "
            "due_date, description) VALUES (?, 'online exam', ?, 100, 0, ?, 'Online exam')",
            (name, row[1], row[3])).lastrowid
    conn.execute("UPDATE exam_portal_exams SET assessment_id = ? WHERE id = ?", (aid, portal_exam_id))
    return aid


def record_online_result(conn, portal_exam_id, student_id, percentage, graded_by=None,
                         scheduler_exam_id=None) -> dict | None:
    aid = assessment_for_portal_exam(conn, portal_exam_id, scheduler_exam_id)
    if aid is None:
        return None
    a = exam_marking.get_settings(conn, aid)
    grade_id = _write_score(conn, aid, a["max_points"], str(student_id), float(percentage), graded_by)
    return exam_marking.after_mark(conn, grade_id, graded_by)


def online_result_visible(conn, portal_exam_id) -> bool:
    """Students see an online exam's score only once its marks are released."""
    row = conn.execute(
        "SELECT a.marks_released_at FROM exam_portal_exams e "
        "LEFT JOIN assessments a ON a.assessment_id = e.assessment_id WHERE e.id = ?",
        (portal_exam_id,)).fetchone()
    return bool(row and row[0])


# ── candidate numbers ───────────────────────────────────────────────────


def candidate_numbers(conn, exam_id, student_ids) -> dict:
    """{student_id: candidate number} for desk cards and anonymous mark entry."""
    aid = assessment_for_exam(conn, exam_id)
    return {str(s): exam_marking.candidate_number(conn, aid, s) for s in student_ids if s}


def is_anonymous(conn, exam_id) -> bool:
    aid = assessment_for_exam(conn, exam_id, create=False)
    return bool(aid) and exam_marking.is_anonymised(conn, aid)
