"""Shared graduation-eligibility check.

Single source of truth for "is this student eligible to graduate?", used by
BOTH the Degree Audit graduation tab (to show PASS/FAIL and gate the "add to
ceremony" action) and the Graduation Ceremony GUI (to refuse RSVPs for students
who aren't eligible). Keeping the rule here stops the two screens drifting apart.

Eligibility = the student has already been approved (``students.status =
'Graduated'``) OR meets the credit / GPA / module thresholds computed from their
enrolled modules — the same calculation the Degree Audit tab has always used.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from education_system.systems.university.infrastructure.database.db import get_connection

# Thresholds — mirror the values the Degree Audit graduation tab uses.
REQUIRED_CREDITS = 120
REQUIRED_GPA = 2.0
REQUIRED_MODULES = 40

_GPA_CASE = (
    "AVG(CASE sm.grade "
    "WHEN 'A' THEN 4.0 WHEN 'B' THEN 3.0 WHEN 'C' THEN 2.0 "
    "WHEN 'D' THEN 1.0 WHEN 'F' THEN 0.0 ELSE NULL END)"
)


def check_eligibility(student_id: str, conn=None) -> Dict[str, Any]:
    """Return an eligibility report for *student_id*.

    Keys: eligible (bool), already_graduated (bool), student_name,
    credits_earned, current_gpa, modules_completed, the matching required_*
    thresholds, the per-check booleans, reasons (list of unmet-requirement
    strings) and — only on failure to compute — ``error`` True.
    """
    student_id = (student_id or "").strip()
    report: Dict[str, Any] = {
        "student_id": student_id,
        "student_name": student_id,
        "eligible": False,
        "already_graduated": False,
        "credits_earned": 0.0,
        "current_gpa": 0.0,
        "modules_completed": 0,
        "required_credits": REQUIRED_CREDITS,
        "required_gpa": REQUIRED_GPA,
        "required_modules": REQUIRED_MODULES,
        "credit_met": False,
        "gpa_met": False,
        "modules_met": False,
        "reasons": [],
        "error": False,
    }
    if not student_id:
        report["reasons"].append("No student selected.")
        return report

    close = conn is None
    conn = conn or get_connection()
    try:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT first_name, last_name, status FROM students WHERE student_id = ?",
            (student_id,)).fetchone()
        if not row:
            report["reasons"].append(f"No student record for {student_id}.")
            return report
        report["student_name"] = f"{row[0] or ''} {row[1] or ''}".strip() or student_id
        report["already_graduated"] = str(row[2] or "").lower() == "graduated"

        prog = cur.execute(
            f"""SELECT COUNT(DISTINCT sm.module_code),
                       SUM(COALESCE(m.credits, 0)),
                       {_GPA_CASE}
                  FROM student_modules sm
                  LEFT JOIN modules m ON sm.module_code = m.module_code
                 WHERE sm.student_id = ?""", (student_id,)).fetchone()
        report["modules_completed"] = int(prog[0] or 0)
        report["credits_earned"] = float(prog[1] or 0)
        report["current_gpa"] = float(prog[2] or 0.0)
    except Exception as exc:
        # Couldn't compute — flag it so callers can warn-and-allow rather than
        # hard-block on an infrastructure/data problem.
        report["error"] = True
        report["reasons"].append(f"Could not verify eligibility: {exc}")
        return report
    finally:
        if close:
            conn.close()

    report["credit_met"] = report["credits_earned"] >= REQUIRED_CREDITS
    report["gpa_met"] = report["current_gpa"] >= REQUIRED_GPA
    report["modules_met"] = report["modules_completed"] >= REQUIRED_MODULES

    if not report["credit_met"]:
        report["reasons"].append(
            f"Needs {REQUIRED_CREDITS - report['credits_earned']:.0f} more credits "
            f"({report['credits_earned']:.0f}/{REQUIRED_CREDITS}).")
    if not report["modules_met"]:
        report["reasons"].append(
            f"Needs {REQUIRED_MODULES - report['modules_completed']} more modules "
            f"({report['modules_completed']}/{REQUIRED_MODULES}).")
    if not report["gpa_met"]:
        report["reasons"].append(
            f"GPA below {REQUIRED_GPA:.1f} ({report['current_gpa']:.2f}).")

    requirements_met = (report["credit_met"] and report["gpa_met"]
                        and report["modules_met"])
    # An approved/graduated student stays eligible even if recomputed metrics
    # later dip (the approval is the authoritative decision).
    report["eligible"] = bool(requirements_met or report["already_graduated"])
    return report


def eligibility_blurb(report: Dict[str, Any]) -> str:
    """One-line human summary for dialogs/logs."""
    if report.get("eligible"):
        if report.get("already_graduated"):
            return "Eligible (already approved/graduated)."
        return "Eligible for graduation."
    if report.get("error"):
        return "Eligibility could not be verified."
    return "Not eligible: " + " ".join(report.get("reasons", []))
