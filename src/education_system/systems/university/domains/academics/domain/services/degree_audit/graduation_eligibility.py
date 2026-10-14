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
        "award_ratified": False,
        "ratified_award": None,
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

        # Mutable grades are advisory only: release requires a currently
        # authorised ratified award.
        board_schema = cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' "
            "AND name = 'ratified_student_awards'"
        ).fetchone()
        if board_schema:
            award = cur.execute(
                """SELECT award_name, classification, academic_year,
                          ratified_at
                     FROM ratified_student_awards
                    WHERE student_id = ? AND status = 'ratified'
                      AND release_authorised = 1
                    ORDER BY ratified_at DESC LIMIT 1""",
                (student_id,),
            ).fetchone()
            report["award_ratified"] = award is not None
            if award:
                report["ratified_award"] = {
                    "award_name": award[0], "classification": award[1],
                    "academic_year": award[2], "ratified_at": award[3],
                }

        # Earned, not enrolled. This used to COUNT every student_modules row
        # and SUM every module's credits, so a student who had merely
        # registered for six 15-credit modules audited as 90 credits earned
        # with nothing marked. See services.degree_audit.progress.
        from education_system.systems.university.domains.academics.domain.services.degree_audit.progress import (
            earned_progress,
        )
        prog = earned_progress(conn, student_id)
        report["modules_completed"] = prog["modules_completed"]
        report["credits_earned"] = prog["credits_earned"]
        report["current_gpa"] = prog["gpa"]
        report["modules_enrolled"] = prog["modules_enrolled"]
        report["credits_enrolled"] = prog["credits_enrolled"]
        report["modules_graded"] = prog["modules_graded"]
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
    report["eligible"] = bool(
        board_schema and (report["award_ratified"] or report["already_graduated"])
    )
    if requirements_met and not report["award_ratified"]:
        report["reasons"].append(
            "Academic requirements appear complete, but no assessment "
            "board has ratified and released the award."
        )
    if not board_schema:
        report["reasons"].append(
            "Assessment-board schema is unavailable; graduation cannot be authorised."
        )
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
