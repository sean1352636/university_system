"""One module result per student, from every kind of assessed work.

Before this there were two calculations writing ``module_grades``: the
Assessment slice's ``update_module_grade`` counted exams and tests (the
``assessments`` table, marks in ``grades``) and the assignment system's
roll-up counted assignments (``assignment_submissions``). Each overwrote the
other's result with half the picture, and Grade Tracking — where most marks
are entered — called neither. This module is the only calculation; both old
entry points now delegate here.

Rules:

* Components are the module's active summative assignments and its active
  assessments (not Draft/Archived). An assessment that mirrors an assignment
  (same title in the same module, which the assessment/assignment sync
  creates) is folded into that assignment so the work counts once: the
  submission mark is used, else a mark entered against the mirror, and the
  mirror's weight applies when the assignment has none.
* Weights are each component's own weighting (``module_weight_pct`` /
  ``weight``). If no component in the module has one, all count equally.
* A resit mark (referral, already capped when entered; or deferral) replaces
  the first attempt. A recorded non-submission or an unexcused exam absence
  (``ABS``) counts as 0. An absence with accepted mitigation (``ABS-MC``)
  leaves the component outstanding.
* The result is provisional until an exam board confirms it; a confirmed
  result is never recalculated.

Functions take an open connection and do not commit, so a caller's grade
write and the recalculation share one transaction.
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.systems.university.application.assessment.classification import PASS_MARK, uk_band

logger = logging.getLogger(__name__)

AWARDING_OUTCOMES = ("pass", "compensated", "condoned")
#: Board decision -> module outcome.
DECISION_OUTCOMES = {
    "pass": "pass", "fail": "fail", "compensate": "compensated",
    "condone": "condoned", "reassess": "referred",
}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _columns(conn, table):
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}


# ── components ──────────────────────────────────────────────────────────


def _assignment_components(conn, module_code):
    cols = _columns(conn, "assignments")
    kind = "COALESCE(assessment_kind, 'summative') = 'summative'" if "assessment_kind" in cols else "1 = 1"
    weight = "module_weight_pct" if "module_weight_pct" in cols else "NULL"
    resit = "reassessment_of IS NULL" if "reassessment_of" in cols else "1 = 1"
    rows = conn.execute(
        f"SELECT id, title, {weight} FROM assignments WHERE module_code = ? "
        f"AND COALESCE(is_active, 1) = 1 AND {kind} AND {resit}", (module_code,)).fetchall()  # nosec B608
    return [{"kind": "assignment", "id": r[0], "title": r[1] or "",
             "weight": float(r[2]) if r[2] else 0.0} for r in rows]


def _assessment_rows(conn, module_code):
    cols = _columns(conn, "assessments")
    if not cols:
        return []
    status = "COALESCE(status, 'Active') NOT IN ('Draft', 'Archived')" if "status" in cols else "1 = 1"
    resit = "reassessment_of IS NULL" if "reassessment_of" in cols else "1 = 1"
    rows = conn.execute(
        f"SELECT assessment_id, assessment_name, weight, max_points FROM assessments "
        f"WHERE module_code = ? AND {status} AND {resit}", (module_code,)).fetchall()  # nosec B608
    return [{"kind": "assessment", "id": r[0], "title": r[1] or "",
             "weight": float(r[2]) if r[2] else 0.0, "max_points": float(r[3] or 100)} for r in rows]


def components(conn, module_code):
    """Every counted component of a module, mirrors folded into their assignment."""
    assignments = _assignment_components(conn, module_code)
    by_title = {a["title"].strip().lower(): a for a in assignments}
    exams = []
    for row in _assessment_rows(conn, module_code):
        twin = by_title.get(row["title"].strip().lower())
        if twin is None:
            exams.append(row)
            continue
        twin["mirror"] = row
        if twin["weight"] <= 0:
            twin["weight"] = row["weight"]
    return assignments + exams


def mirrored_assessments(conn, module_code):
    """Assessments folded into an assignment of the same name."""
    return [c["mirror"]["title"] for c in components(conn, module_code) if c.get("mirror")]


# ── marks ───────────────────────────────────────────────────────────────


def _assignment_mark(conn, comp, student_id):
    resit = conn.execute(
        "SELECT s.grade FROM assignment_reassessments r "
        "JOIN assignment_submissions s ON s.assignment_id = r.reassessment_assignment_id "
        "     AND s.student_id = r.student_id "
        "WHERE r.original_assignment_id = ? AND r.student_id = ? AND s.grade IS NOT NULL "
        "ORDER BY r.reassessment_assignment_id DESC, COALESCE(s.is_final_submission, 1) DESC, s.id DESC "
        "LIMIT 1", (comp["id"], student_id)).fetchone() if _columns(conn, "assignment_reassessments") else None
    if resit:
        return float(resit[0]), "resit"
    sub = conn.execute(
        "SELECT grade FROM assignment_submissions WHERE assignment_id = ? AND student_id = ? "
        "AND grade IS NOT NULL ORDER BY COALESCE(is_final_submission, 1) DESC, "
        "COALESCE(version_number, 1) DESC, id DESC LIMIT 1", (comp["id"], student_id)).fetchone()
    if sub:
        return float(sub[0]), "marked"
    if comp.get("mirror"):
        mark, state = _assessment_mark(conn, comp["mirror"], student_id)
        if state != "missing":
            return mark, state
    if _columns(conn, "assignment_non_submissions") and conn.execute(
            "SELECT 1 FROM assignment_non_submissions WHERE assignment_id = ? AND student_id = ? "
            "AND voided = 0", (comp["id"], student_id)).fetchone():
        return 0.0, "ns"
    return None, "missing"


def _grade_to_mark(row, max_points):
    """(mark, state) from a grades row of (score, result_code)."""
    code = (row[1] or "").upper() if row[1] else ""
    if code == "ABS":
        return 0.0, "absent"
    if code == "ABS-MC":
        return None, "absent_mc"
    if row[0] is None:
        return None, "missing"
    return round(float(row[0]) / (max_points or 100) * 100, 2), "marked"


def _assessment_mark(conn, comp, student_id):
    has_code = "result_code" in _columns(conn, "grades")
    code_col = "g.result_code" if has_code else "NULL"
    if _columns(conn, "exam_reassessments"):
        resit = conn.execute(
            f"SELECT g.score, {code_col}, a.max_points FROM exam_reassessments r "
            f"JOIN assessments a ON a.assessment_id = r.reassessment_assessment_id "
            f"JOIN grades g ON g.assessment_id = a.assessment_id AND g.student_id = r.student_id "
            f"WHERE r.original_assessment_id = ? AND r.student_id = ? "
            f"ORDER BY a.assessment_id DESC, g.grade_id DESC LIMIT 1",
            (comp["id"], student_id)).fetchone()  # nosec B608
        if resit:
            mark, state = _grade_to_mark(resit, float(resit[2] or 100))
            if state != "missing":
                return mark, "resit" if state == "marked" else state
    row = conn.execute(
        f"SELECT g.score, {code_col} FROM grades g WHERE g.assessment_id = ? AND g.student_id = ? "
        f"ORDER BY g.grade_id DESC LIMIT 1", (comp["id"], student_id)).fetchone()  # nosec B608
    if row is None:
        return None, "missing"
    return _grade_to_mark(row, comp["max_points"])


def component_mark(conn, comp, student_id):
    if comp["kind"] == "assignment":
        return _assignment_mark(conn, comp, str(student_id))
    return _assessment_mark(conn, comp, str(student_id))


# ── the result ──────────────────────────────────────────────────────────


def calculate(conn, student_id, module_code) -> dict | None:
    """The module result as a dict, without writing it. None if nothing is marked."""
    comps = components(conn, module_code)
    if not comps:
        return None
    weighted = any(c["weight"] > 0 for c in comps)
    total = weight_marked = 0.0
    states, resit_used = [], False
    for comp in comps:
        weight = comp["weight"] if weighted else 1.0
        if weight <= 0:
            continue
        mark, state = component_mark(conn, comp, student_id)
        states.append(state)
        resit_used = resit_used or state == "resit"
        if mark is not None:
            total += mark * weight
            weight_marked += weight
    if weight_marked <= 0:
        return None
    final = round(total / weight_marked, 2)
    complete = not any(s in ("missing", "absent_mc") for s in states)
    if "absent_mc" in states:
        outcome = "deferred"
    elif not complete:
        outcome = "incomplete"
    else:
        outcome = "pass" if final >= PASS_MARK else "fail"
    return {"final_score": final, "final_grade": uk_band(final), "is_complete": complete,
            "outcome": outcome, "attempt": 2 if resit_used else 1}


def recompute(conn, student_id, module_code) -> dict | None:
    """Recalculate and store one student's module result (unless confirmed)."""
    student_id = str(student_id)
    existing = conn.execute(
        "SELECT id, COALESCE(status, 'provisional') FROM module_grades "
        "WHERE student_id = ? AND module_code = ? ORDER BY id LIMIT 1",
        (student_id, module_code)).fetchone()
    if existing and existing[1] == "confirmed":
        return None
    result = calculate(conn, student_id, module_code)
    if result is None:
        return None
    now = _now()
    completion = now[:10] if result["is_complete"] else None
    # A resit mark arriving for an awaiting_resit result makes it provisional
    # again for the next board; first-sit marks stay locked.
    status = "provisional" if not existing or existing[1] != "awaiting_resit" or result["attempt"] == 2 \
        else "awaiting_resit"
    values = (result["final_score"], result["final_grade"], completion, now, result["outcome"],
              result["attempt"], 1 if result["is_complete"] else 0, status)
    if existing:
        conn.execute(
            "UPDATE module_grades SET final_score = ?, final_grade = ?, completion_date = ?, "
            "date_recorded = ?, outcome = ?, attempt = ?, is_complete = ?, status = ? WHERE id = ?",
            (*values, existing[0]))
    else:
        conn.execute(
            "INSERT INTO module_grades (final_score, final_grade, completion_date, date_recorded, "
            "outcome, attempt, is_complete, status, student_id, module_code) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (*values, student_id, module_code))
    return {**result, "status": status}


def recompute_safely(conn, student_id, module_code):
    """recompute(), logging instead of raising — for best-effort callers."""
    try:
        return recompute(conn, student_id, module_code)
    except Exception:
        logger.warning("Module result not recalculated for %s/%s", student_id, module_code,
                       exc_info=True)
        return None


def module_of(conn, kind, component_id):
    if kind == "assignment":
        row = conn.execute("SELECT module_code FROM assignments WHERE id = ?", (component_id,)).fetchone()
    else:
        row = conn.execute("SELECT module_code FROM assessments WHERE assessment_id = ?",
                           (component_id,)).fetchone()
    return row[0] if row else None


def recompute_module(conn, module_code) -> int:
    """Recalculate every enrolled student on a module. Returns how many changed."""
    students = [r[0] for r in conn.execute(
        "SELECT DISTINCT student_id FROM student_modules WHERE module_code = ? "
        "AND student_id IS NOT NULL", (module_code,))]
    return sum(1 for sid in students if recompute_safely(conn, sid, module_code))


# ── weights ─────────────────────────────────────────────────────────────


def weight_report(conn, module_code=None) -> list[dict]:
    """Per module: assignment and exam weightings, their total, and mirrors."""
    if module_code:
        modules = [module_code]
    else:
        modules = sorted({r[0] for r in conn.execute(
            "SELECT module_code FROM assignments WHERE COALESCE(is_active, 1) = 1 "
            "UNION SELECT module_code FROM assessments") if r[0]})
    report = []
    for code in modules:
        comps = components(conn, code)
        if not comps:
            continue
        a_total = sum(c["weight"] for c in comps if c["kind"] == "assignment")
        e_total = sum(c["weight"] for c in comps if c["kind"] == "assessment")
        unweighted = [c["title"] for c in comps if c["weight"] <= 0]
        total = a_total + e_total
        if total == 0:
            state = "equal weights"
        elif abs(total - 100) < 0.01 and not unweighted:
            state = "ok"
        else:
            state = "check"
        report.append({"module_code": code, "assignments_pct": a_total, "exams_pct": e_total,
                       "total_pct": total, "unweighted": unweighted,
                       "mirrors": mirrored_assessments(conn, code), "state": state})
    return report


# ── board confirmation and locks ────────────────────────────────────────


def is_locked(conn, student_id, module_code) -> bool:
    if "locked" not in _columns(conn, "module_grades"):
        return False
    return conn.execute(
        "SELECT 1 FROM module_grades WHERE student_id = ? AND module_code = ? AND locked = 1",
        (str(student_id), module_code)).fetchone() is not None


def _award_credits(conn, student_id, module_code, final_score):
    credits = conn.execute("SELECT COALESCE(credits, 0) FROM modules WHERE module_code = ?",
                           (module_code,)).fetchone()
    credits = float(credits[0]) if credits else 0.0
    conn.execute(
        "UPDATE student_modules SET grade = ?, credits_earned = ?, status = 'Completed', "
        "completion_date = COALESCE(completion_date, ?) WHERE student_id = ? AND module_code = ?",
        (f"{final_score:.2f}", int(credits), _now()[:10], student_id, module_code))
    return credits


def _confirm_one(conn, board_id, student_id, module_code, decision):
    row = conn.execute(
        "SELECT id, final_score, is_complete, outcome FROM module_grades "
        "WHERE student_id = ? AND module_code = ? ORDER BY id LIMIT 1",
        (student_id, module_code)).fetchone()
    if row is None or row[1] is None:
        return None
    outcome = DECISION_OUTCOMES.get(decision) if decision else None
    if outcome is None:
        if not row[2]:
            return None  # incomplete / deferred: nothing to confirm yet
        outcome = "pass" if row[1] >= PASS_MARK else "fail"
    credits = _award_credits(conn, student_id, module_code, row[1]) if outcome in AWARDING_OUTCOMES else 0.0
    if outcome not in AWARDING_OUTCOMES:
        conn.execute("UPDATE student_modules SET grade = ? WHERE student_id = ? AND module_code = ?",
                     (f"{row[1]:.2f}", student_id, module_code))
    status = "awaiting_resit" if outcome == "referred" else "confirmed"
    conn.execute(
        "UPDATE module_grades SET outcome = ?, credits_awarded = ?, board_id = ?, status = ?, "
        "locked = 1, confirmed_at = ? WHERE id = ?",
        (outcome, credits, board_id, status, _now(), row[0]))
    return outcome


def confirm_results(conn, board_id, student_id, module_codes=None, decisions=None) -> dict:
    """Lock and confirm a student's module results for a board.

    ``decisions`` maps module_code -> board decision type; modules without
    one pass or fail on their mark. Passing outcomes award the module's
    credits on the enrolment. A 'reassess' decision locks the first-sit
    marks but leaves the result open for the resit.
    """
    student_id = str(student_id)
    decisions = decisions or {}
    if module_codes is None:
        module_codes = [r[0] for r in conn.execute(
            "SELECT module_code FROM module_grades WHERE student_id = ? "
            "AND COALESCE(status, 'provisional') IN ('provisional', 'awaiting_resit')",
            (student_id,))]
    return {code: _confirm_one(conn, board_id, student_id, code, decisions.get(code))
            for code in module_codes}


def unlock_board(conn, board_id) -> int:
    """Reopening a board unlocks the results it confirmed (credits are kept
    until the board confirms again)."""
    cur = conn.execute(
        "UPDATE module_grades SET locked = 0, status = 'provisional' WHERE board_id = ?",
        (board_id,))
    return cur.rowcount
