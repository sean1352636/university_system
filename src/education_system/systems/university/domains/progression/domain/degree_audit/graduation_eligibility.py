"""Shared graduation-eligibility check, for Degree Audit and the Graduation
window.

The rule lives in ``university/application/graduation/eligibility``:
eligible means an assessment board has ratified and released the award and
nothing blocks it (graduation holds, open misconduct cases). This wrapper
keeps the report shape the screens already read. Credits are shown against
the programme's own award rule; there is no GPA or module-count
requirement in UK awards, so those checks always pass and are labelled as
advisory.
"""

from __future__ import annotations

from typing import Any, Dict

from education_system.systems.university.infrastructure.database.db import get_connection


def check_eligibility(student_id: str, conn=None) -> Dict[str, Any]:
    """Eligibility report for *student_id* (see the module docstring)."""
    from education_system.systems.university.application.graduation import eligibility as rules

    student_id = (student_id or "").strip()
    report: Dict[str, Any] = {
        "student_id": student_id, "student_name": student_id, "eligible": False,
        "already_graduated": False, "award_ratified": False, "ratified_award": None,
        "credits_earned": 0.0, "current_gpa": 0.0, "modules_completed": 0,
        "required_credits": rules.DEFAULT_CREDITS, "required_gpa": 0.0, "required_modules": 0,
        "credit_met": False, "gpa_met": True, "modules_met": True, "reasons": [],
        "warnings": [], "error": False,
    }
    if not student_id:
        report["reasons"].append("No student selected.")
        return report
    close = conn is None
    conn = conn or get_connection(row_factory=False)
    try:
        try:
            result = rules.check(conn, student_id)
        except ValueError:
            report["reasons"].append(f"No student record for {student_id}.")
            return report
        from education_system.systems.university.domains.progression.domain.degree_audit.progress import (  # noqa: E501
            earned_progress,
        )
        progress = earned_progress(conn, student_id)
        if close:
            conn.commit()       # ensure() may have created the graduation tables
    except Exception as exc:
        report["error"] = True
        report["reasons"].append(f"Could not verify eligibility: {exc}")
        return report
    finally:
        if close:
            conn.close()
    award = result["award"]
    report.update(
        student_name=result["student_name"], eligible=result["eligible"],
        already_graduated=result["conferral"] is not None,
        award_ratified=award is not None,
        ratified_award=None if award is None else {
            "award_name": award["award_name"], "classification": award.get("classification"),
            "academic_year": award.get("academic_year"), "ratified_at": award.get("ratified_at")},
        credits_earned=result["credits_earned"], required_credits=result["credits_required"],
        credit_met=result["credits_earned"] >= result["credits_required"],
        current_gpa=float(progress.get("gpa") or 0), modules_completed=progress["modules_completed"],
        modules_enrolled=progress.get("modules_enrolled"),
        credits_enrolled=progress.get("credits_enrolled"),
        modules_graded=progress.get("modules_graded"),
        reasons=list(result["blockers"]), warnings=list(result["warnings"]),
        certificate_name=result["certificate_name"], name_confirmed=result["name_confirmed"],
    )
    return report


def eligibility_blurb(report: Dict[str, Any]) -> str:
    """One-line human summary for dialogs/logs."""
    if report.get("eligible"):
        return "Eligible for graduation."
    if report.get("already_graduated"):
        return "Award already conferred."
    if report.get("error"):
        return "Eligibility could not be verified."
    return "Not eligible: " + " ".join(report.get("reasons", []))
