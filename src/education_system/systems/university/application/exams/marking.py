"""Exam and test marking control — the counterpart of the assignment QA rules.

Exams, tests, presentations and practicals live in ``assessments`` with marks
in ``grades`` (``score`` out of ``max_points``). Grade Tracking (Academics)
and the grade CLI (Assessment) both enter those marks, so the rules sit here
where both slices may call them:

* anonymous marking: candidate numbers instead of names until release
* absence codes: ``ABS`` (counts as 0, referral) and ``ABS-MC`` (accepted
  mitigation: outstanding, deferral)
* moderation: sample, second mark, agree
* release: marks are hidden from students until the assessment is released
* resits: referral capped at the pass mark, deferral uncapped
* every change to an existing mark needs a recorded reason

Functions take an open connection and never commit: the caller's own write
and these rules share one transaction.
"""

from __future__ import annotations

import math
import random
import secrets
from datetime import datetime

from education_system.systems.university.application.assessment import module_results
from education_system.systems.university.application.assessment.outcomes import (
    appeal_uncapped_resit,
    uncapped_resit_claim,
)
from education_system.systems.university.application.assessment.classification import PASS_MARK

ABSENCE_CODES = {"ABS": "Absent (counts as 0)", "ABS-MC": "Absent with accepted mitigation"}
MIN_MODERATION_SAMPLE = 5
RESIT_TYPES = ("referral", "deferral")
#: SQL: is grade row g on assessment a visible to the student?
VISIBLE_SQL = "(a.marks_released_at IS NOT NULL OR g.released_at IS NOT NULL)"

_SETTINGS = {
    "anonymous_marking": lambda v: 1 if v else 0,
    "moderation_required": lambda v: 1 if v else 0,
    "moderation_sample_pct": lambda v: float(v or 0),
}


class ExamMarkingError(ValueError):
    """A marking rule refused the action; the message is safe to show."""


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _assessment(conn, assessment_id) -> dict:
    cur = conn.execute("SELECT * FROM assessments WHERE assessment_id = ?", (assessment_id,))
    row = cur.fetchone()
    if row is None:
        raise ExamMarkingError(f"Assessment {assessment_id} not found.")
    return dict(zip([d[0] for d in cur.description], row))


def _pct(score, max_points):
    return round(float(score) / (float(max_points or 100)) * 100, 2)


# ── settings and anonymity ──────────────────────────────────────────────


def get_settings(conn, assessment_id) -> dict:
    return _assessment(conn, assessment_id)


def update_settings(conn, assessment_id, **fields) -> dict:
    unknown = set(fields) - set(_SETTINGS)
    if unknown:
        raise ExamMarkingError(f"Unknown setting(s): {', '.join(sorted(unknown))}")
    _assessment(conn, assessment_id)
    values = {k: _SETTINGS[k](v) for k, v in fields.items()}
    if values:
        sets = ", ".join(f'"{k}" = ?' for k in values)
        conn.execute(f"UPDATE assessments SET {sets} WHERE assessment_id = ?",  # nosec B608 - whitelisted
                     (*values.values(), assessment_id))
    return _assessment(conn, assessment_id)


def is_anonymised(conn, assessment_id) -> bool:
    a = _assessment(conn, assessment_id)
    return bool(a.get("anonymous_marking")) and not a.get("marks_released_at")


def candidate_number(conn, assessment_id, student_id) -> str:
    row = conn.execute(
        "SELECT candidate_number FROM exam_candidate_numbers WHERE assessment_id = ? AND student_id = ?",
        (assessment_id, str(student_id))).fetchone()
    if row:
        return row[0]
    taken = {r[0] for r in conn.execute(
        "SELECT candidate_number FROM exam_candidate_numbers WHERE assessment_id = ?", (assessment_id,))}
    code = f"E{secrets.randbelow(900000) + 100000}"
    while code in taken:
        code = f"E{secrets.randbelow(900000) + 100000}"
    conn.execute(
        "INSERT INTO exam_candidate_numbers (assessment_id, student_id, candidate_number, created_at) "
        "VALUES (?, ?, ?, ?)", (assessment_id, str(student_id), code, _now()))
    return code


def marker_label(conn, assessment_id, student_id, name) -> str:
    """The student's name, or 'Candidate E123456' while marking is anonymous."""
    if is_anonymised(conn, assessment_id):
        return f"Candidate {candidate_number(conn, assessment_id, student_id)}"
    return name


# ── marks, absences, change reasons ─────────────────────────────────────


def log_change(conn, *, source, record_id, student_id, module_code, old_value, new_value,
               reason, changed_by=None) -> None:
    """Record why a mark changed. A blank reason is refused."""
    if not (reason or "").strip():
        raise ExamMarkingError("A reason is required to change or remove a recorded mark.")
    conn.execute(
        "INSERT INTO grade_change_log (source, record_id, student_id, module_code, old_value, "
        "new_value, reason, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (source, record_id, str(student_id) if student_id else None, module_code,
         None if old_value is None else str(old_value), None if new_value is None else str(new_value),
         reason.strip(), changed_by, _now()))


def change_log(conn, student_id=None, module_code=None, limit=200) -> list[dict]:
    where, params = [], []
    if student_id:
        where.append("student_id = ?")
        params.append(str(student_id))
    if module_code:
        where.append("module_code = ?")
        params.append(module_code)
    cur = conn.execute(
        "SELECT * FROM grade_change_log " + ("WHERE " + " AND ".join(where) + " " if where else "")
        + "ORDER BY id DESC LIMIT ?", (*params, limit))  # nosec B608 - fixed clauses
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _referral_cap(conn, assessment_id, student_id):
    row = conn.execute(
        "SELECT attempt_type, mark_cap_pct FROM exam_reassessments "
        "WHERE reassessment_assessment_id = ? AND student_id = ?",
        (assessment_id, str(student_id))).fetchone()
    if row and row[0] == "referral":
        return float(row[1] if row[1] is not None else PASS_MARK)
    return None


def after_mark(conn, grade_id, marker=None) -> dict:
    """Apply the rules to a grades row the caller has just written.

    Caps a referral resit at the pass mark (keeping the marker's score in
    ``raw_score``), keeps a moderation sample's first mark current, and
    recalculates the module result. Returns what was stored and whether the
    student can see it.
    """
    row = conn.execute(
        "SELECT g.student_id, g.assessment_id, g.score, a.max_points, a.module_code, "
        "       a.marks_released_at, g.released_at "
        "FROM grades g JOIN assessments a ON a.assessment_id = g.assessment_id WHERE g.grade_id = ?",
        (grade_id,)).fetchone()
    if row is None:
        raise ExamMarkingError(f"Grade {grade_id} not found.")
    student_id, assessment_id, score, max_points, module_code, released_at, g_released = row
    capped = False
    if score is not None:
        cap = _referral_cap(conn, assessment_id, student_id)
        pct = _pct(score, max_points)
        if cap is not None and pct > cap:
            conn.execute("UPDATE grades SET raw_score = ?, score = ?, capped = 1, result_code = NULL "
                         "WHERE grade_id = ?",
                         (score, round(cap * float(max_points or 100) / 100, 2), grade_id))
            capped = True
        else:
            # A real score replaces any absence code recorded earlier.
            conn.execute("UPDATE grades SET raw_score = ?, capped = 0, result_code = NULL "
                         "WHERE grade_id = ?",
                         (score, grade_id))
        conn.execute(
            "UPDATE exam_moderation SET first_mark = ?, updated_at = ? "
            "WHERE grade_id = ? AND status = 'sampled' AND second_mark IS NULL",
            (pct, _now(), grade_id))
    released = bool(released_at)
    if released and not g_released:
        conn.execute("UPDATE grades SET released_at = ? WHERE grade_id = ?", (_now(), grade_id))
    module_results.recompute_safely(conn, student_id, module_code)
    return {"capped": capped, "released": released}


def record_absence(conn, assessment_id, student_id, code, recorded_by=None, reason=None) -> int:
    """Record ABS or ABS-MC for a student instead of a score."""
    code = (code or "").upper()
    if code not in ABSENCE_CODES:
        raise ExamMarkingError(f"Absence code must be one of {', '.join(ABSENCE_CODES)}.")
    a = _assessment(conn, assessment_id)
    existing = conn.execute(
        "SELECT grade_id, score, result_code FROM grades WHERE assessment_id = ? AND student_id = ? "
        "ORDER BY grade_id DESC LIMIT 1", (assessment_id, str(student_id))).fetchone()
    if existing and (existing[1] is not None or existing[2]):
        log_change(conn, source="grades", record_id=existing[0], student_id=student_id,
                   module_code=a["module_code"], old_value=existing[2] or existing[1],
                   new_value=code, reason=reason or "", changed_by=recorded_by)
    if existing:
        conn.execute("UPDATE grades SET score = NULL, result_code = ?, letter_grade = ?, "
                     "comments = COALESCE(?, comments) WHERE grade_id = ?",
                     (code, code, reason, existing[0]))
        grade_id = existing[0]
    else:
        cur = conn.execute(
            "INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date, "
            "comments, result_code) VALUES (?, ?, NULL, ?, ?, ?, ?)",
            (str(student_id), assessment_id, code, _now()[:10], reason or ABSENCE_CODES[code], code))
        grade_id = cur.lastrowid
    module_results.recompute_safely(conn, student_id, a["module_code"])
    return grade_id


# ── moderation ──────────────────────────────────────────────────────────


def draw_sample(conn, assessment_id, sample_pct=None) -> int:
    """Every fail plus a random spread, at least five scripts (or all)."""
    a = _assessment(conn, assessment_id)
    if a.get("marks_released_at"):
        raise ExamMarkingError("Marks are already released.")
    pct = float(sample_pct if sample_pct is not None else a.get("moderation_sample_pct") or 10)
    marked = [(r[0], _pct(r[1], a["max_points"]), r[2]) for r in conn.execute(
        "SELECT grade_id, score, graded_by FROM grades WHERE assessment_id = ? AND score IS NOT NULL",
        (assessment_id,))]
    if not marked:
        raise ExamMarkingError("Nothing has been marked yet.")
    target = max(MIN_MODERATION_SAMPLE, math.ceil(len(marked) * pct / 100))
    fails = [m for m in marked if m[1] < PASS_MARK]
    rest = [m for m in marked if m[1] >= PASS_MARK]
    random.shuffle(rest)
    now = _now()
    for grade_id, mark, marker in fails + rest[:max(0, target - len(fails))]:
        conn.execute(
            "INSERT OR IGNORE INTO exam_moderation (assessment_id, grade_id, first_mark, first_marker, "
            "status, created_at, updated_at) VALUES (?, ?, ?, ?, 'sampled', ?, ?)",
            (assessment_id, grade_id, mark, marker, now, now))
    conn.execute("UPDATE assessments SET moderation_status = 'in_progress' WHERE assessment_id = ?",
                 (assessment_id,))
    return conn.execute("SELECT COUNT(*) FROM exam_moderation WHERE assessment_id = ?",
                        (assessment_id,)).fetchone()[0]


def moderation_rows(conn, assessment_id) -> list[dict]:
    anonymous = is_anonymised(conn, assessment_id)
    rows = conn.execute(
        "SELECT m.id, g.student_id, m.first_mark, m.second_mark, m.agreed_mark, m.status "
        "FROM exam_moderation m JOIN grades g ON g.grade_id = m.grade_id "
        "WHERE m.assessment_id = ? ORDER BY m.first_mark", (assessment_id,)).fetchall()
    out = []
    for r in rows:
        label = f"Candidate {candidate_number(conn, assessment_id, r[1])}" if anonymous else r[1]
        diff = abs(r[2] - r[3]) if r[2] is not None and r[3] is not None else None
        out.append({"id": r[0], "label": label, "first_mark": r[2], "second_mark": r[3],
                    "difference": diff, "agreed_mark": r[4], "status": r[5]})
    return out


def record_second_mark(conn, moderation_id, mark, marker=None, notes=None) -> None:
    mark = float(mark)
    if not 0 <= mark <= 100:
        raise ExamMarkingError("Second mark must be a percentage from 0 to 100.")
    row = conn.execute("SELECT status FROM exam_moderation WHERE id = ?", (moderation_id,)).fetchone()
    if row is None:
        raise ExamMarkingError("Moderation record not found.")
    if row[0] == "agreed":
        raise ExamMarkingError("This script already has an agreed mark.")
    conn.execute("UPDATE exam_moderation SET second_mark = ?, second_marker = ?, "
                 "notes = COALESCE(?, notes), status = 'second_marked', updated_at = ? WHERE id = ?",
                 (mark, marker, notes, _now(), moderation_id))


def agree_mark(conn, moderation_id, agreed, agreed_by=None, notes=None) -> None:
    """Settle a sampled script; a changed mark is written back to the grade."""
    agreed = float(agreed)
    if not 0 <= agreed <= 100:
        raise ExamMarkingError("Agreed mark must be a percentage from 0 to 100.")
    row = conn.execute(
        "SELECT m.grade_id, m.first_mark, m.second_mark, g.student_id, a.max_points, a.module_code "
        "FROM exam_moderation m JOIN grades g ON g.grade_id = m.grade_id "
        "JOIN assessments a ON a.assessment_id = m.assessment_id WHERE m.id = ?",
        (moderation_id,)).fetchone()
    if row is None:
        raise ExamMarkingError("Moderation record not found.")
    grade_id, first, second, student_id, max_points, module_code = row
    if second is None:
        raise ExamMarkingError("Record a second mark before agreeing one.")
    conn.execute("UPDATE exam_moderation SET agreed_mark = ?, agreed_by = ?, notes = COALESCE(?, notes), "
                 "status = 'agreed', updated_at = ? WHERE id = ?",
                 (agreed, agreed_by, notes, _now(), moderation_id))
    if first is None or abs(agreed - first) > 1e-9:
        log_change(conn, source="grades", record_id=grade_id, student_id=student_id,
                   module_code=module_code, old_value=first, new_value=agreed,
                   reason=notes or "Agreed mark after second marking", changed_by=agreed_by)
        conn.execute("UPDATE grades SET score = ? WHERE grade_id = ?",
                     (round(agreed * float(max_points or 100) / 100, 2), grade_id))
        after_mark(conn, grade_id)


def complete_moderation(conn, assessment_id) -> None:
    total, agreed = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(status = 'agreed'), 0) FROM exam_moderation "
        "WHERE assessment_id = ?", (assessment_id,)).fetchone()
    if not total:
        raise ExamMarkingError("Draw a moderation sample first.")
    if agreed < total:
        raise ExamMarkingError(f"{total - agreed} sampled script(s) have no agreed mark yet.")
    conn.execute("UPDATE assessments SET moderation_status = 'complete' WHERE assessment_id = ?",
                 (assessment_id,))


# ── release ─────────────────────────────────────────────────────────────


def unmarked_students(conn, assessment_id) -> list[str]:
    a = _assessment(conn, assessment_id)
    cohort = [r[0] for r in conn.execute(
        "SELECT DISTINCT student_id FROM student_modules WHERE module_code = ? "
        "AND LOWER(COALESCE(status, 'enrolled')) IN ('enrolled', 'completed')", (a["module_code"],))]
    if a.get("reassessment_of"):
        cohort = [r[0] for r in conn.execute(
            "SELECT student_id FROM exam_reassessments WHERE reassessment_assessment_id = ?",
            (assessment_id,))]
    recorded = {r[0] for r in conn.execute(
        "SELECT student_id FROM grades WHERE assessment_id = ? "
        "AND (score IS NOT NULL OR result_code IS NOT NULL)", (assessment_id,))}
    return [s for s in cohort if s not in recorded]


def release_blockers(conn, assessment_id) -> list[str]:
    a = _assessment(conn, assessment_id)
    if a.get("marks_released_at"):
        return ["Marks are already released."]
    blockers = []
    missing = unmarked_students(conn, assessment_id)
    if missing:
        blockers.append(f"{len(missing)} enrolled student(s) have no mark or absence code.")
    if a.get("moderation_required") and a.get("moderation_status") != "complete":
        blockers.append("Moderation is not complete.")
    return blockers


def release(conn, assessment_id, released_by=None, force=False) -> list[dict]:
    """Release every mark on an assessment. Returns the released rows for notifying."""
    blockers = release_blockers(conn, assessment_id)
    if blockers and not (force and blockers[0] != "Marks are already released."):
        raise ExamMarkingError(" ".join(blockers))
    now = _now()
    conn.execute("UPDATE assessments SET marks_released_at = ?, marks_released_by = ? "
                 "WHERE assessment_id = ?", (now, released_by, assessment_id))
    conn.execute("UPDATE grades SET released_at = COALESCE(released_at, ?) WHERE assessment_id = ?",
                 (now, assessment_id))
    cur = conn.execute(
        "SELECT g.grade_id, g.student_id, g.score, g.result_code, g.comments, s.email_address, "
        "       s.first_name FROM grades g LEFT JOIN students s ON s.student_id = g.student_id "
        "WHERE g.assessment_id = ?", (assessment_id,))
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    _mirror_to_transcript(conn, _assessment(conn, assessment_id), rows, released_by)
    return rows


def _mirror_to_transcript(conn, a, rows, released_by) -> None:
    """Released marks go to ``student_grades``, which transcripts read."""
    cols = {r[1] for r in conn.execute('PRAGMA table_info("student_grades")')}
    if not cols:
        return
    for r in rows:
        if r["result_code"]:
            grade, pct = r["result_code"], 0.0 if r["result_code"] == "ABS" else None
        elif r["score"] is not None:
            pct = _pct(r["score"], a["max_points"])
            grade = f"{pct:.1f}%"
        else:
            continue
        existing = conn.execute(
            "SELECT id FROM student_grades WHERE student_id = ? AND module_code = ? "
            "AND assessment_name = ? LIMIT 1",
            (r["student_id"], a["module_code"], a["assessment_name"])).fetchone()
        if existing:
            conn.execute("UPDATE student_grades SET grade = ?, grade_value = ?, percentage = ?, "
                         "grade_date = date('now'), is_final = 1, instructor = COALESCE(?, instructor) "
                         "WHERE id = ?", (grade, grade, pct, released_by, existing[0]))
        else:
            conn.execute(
                "INSERT INTO student_grades (student_id, module_code, assessment_name, grade, grade_value, "
                "percentage, assessment_type, assessment_date, grade_date, instructor, is_final) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, date('now'), ?, 1)",
                (r["student_id"], a["module_code"], a["assessment_name"], grade, grade, pct,
                 a.get("assessment_type"), a.get("due_date"), released_by))


# ── resits ──────────────────────────────────────────────────────────────


def resit_candidates(conn, assessment_id) -> list[dict]:
    """Fails and absences, with the attempt each is due."""
    a = _assessment(conn, assessment_id)
    if a.get("reassessment_of"):
        raise ExamMarkingError("Arrange resits from the original assessment.")
    already = {r[0] for r in conn.execute(
        "SELECT student_id FROM exam_reassessments WHERE original_assessment_id = ?", (assessment_id,))}
    out = []
    for student_id, score, code in conn.execute(
            "SELECT student_id, score, result_code FROM grades WHERE assessment_id = ?", (assessment_id,)):
        if student_id in already:
            continue
        mark = _pct(score, a["max_points"]) if score is not None else None
        if code == "ABS-MC":
            out.append({"student_id": student_id, "mark": None, "reason": "absent (mitigation)",
                        "suggested_type": "deferral", "mc_claim_id": None})
        elif code == "ABS" or (mark is not None and mark < PASS_MARK):
            claim = uncapped_resit_claim(student_id, a["module_code"])
            # An upheld academic appeal can also grant the uncapped sitting.
            appeal = appeal_uncapped_resit(student_id, a["module_code"])
            out.append({"student_id": student_id, "mark": mark,
                        "reason": "absent" if code == "ABS" else "fail",
                        "suggested_type": "deferral" if claim or appeal else "referral",
                        "mc_claim_id": claim, "appeal_id": appeal})
    return out


def create_resit(conn, assessment_id, students, due_date, created_by=None) -> int:
    """A resit sitting for the given students; its mark replaces the original."""
    if not students:
        raise ExamMarkingError("Choose at least one student.")
    if any(s.get("attempt_type") not in RESIT_TYPES for s in students):
        raise ExamMarkingError(f"Attempt type must be one of {', '.join(RESIT_TYPES)}.")
    a = _assessment(conn, assessment_id)
    if a.get("reassessment_of"):
        raise ExamMarkingError("Arrange resits from the original assessment.")
    kinds = {s["attempt_type"] for s in students}
    cur = conn.execute(
        "INSERT INTO assessments (assessment_name, assessment_type, module_code, max_points, weight, "
        "due_date, description, reassessment_of, reassessment_type, anonymous_marking, "
        "moderation_required) VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)",
        (f"{a['assessment_name']} — Resit", a["assessment_type"], a["module_code"], a["max_points"],
         due_date, a.get("description"), assessment_id, kinds.pop() if len(kinds) == 1 else "mixed",
         a.get("anonymous_marking") or 0, a.get("moderation_required") or 0))
    new_id = cur.lastrowid
    for s in students:
        conn.execute(
            "INSERT INTO exam_reassessments (original_assessment_id, reassessment_assessment_id, "
            "student_id, attempt_type, mark_cap_pct, mc_claim_id, created_at, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (assessment_id, new_id, str(s["student_id"]), s["attempt_type"],
             PASS_MARK if s["attempt_type"] == "referral" else None, s.get("mc_claim_id"),
             _now(), created_by))
    return new_id


def resits(conn, assessment_id) -> list[dict]:
    cur = conn.execute(
        "SELECT r.student_id, r.attempt_type, a.assessment_name, a.due_date, g.score, g.result_code, "
        "       a.max_points FROM exam_reassessments r "
        "JOIN assessments a ON a.assessment_id = r.reassessment_assessment_id "
        "LEFT JOIN grades g ON g.assessment_id = a.assessment_id AND g.student_id = r.student_id "
        "WHERE r.original_assessment_id = ? ORDER BY r.id", (assessment_id,))
    out = []
    for sid, kind, name, due, score, code, max_points in cur.fetchall():
        mark = code if code else (_pct(score, max_points) if score is not None else None)
        out.append({"student_id": sid, "attempt_type": kind, "name": name, "due_date": due, "mark": mark})
    return out
