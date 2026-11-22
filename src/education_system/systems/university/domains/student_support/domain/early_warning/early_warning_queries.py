"""Read queries and the support alert behind the Early Warning screens.

These were inline SQL in the Early Warning Tk window. Lifted here,
unchanged, so the window and the CLI share them; the write paths are
still the managers (``RiskAssessmentManager``, ``InterventionManager``,
``CoachingManager``, ``TutoringManager``, ``IndicatorManager``).

Every function returns plain dicts.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

__all__ = [
    "all_student_ids", "student_picker", "active_coaches", "coaches_with_load",
    "active_coach_assignments", "active_assignment_coach", "tutoring_recommendations",
    "risk_indicators", "send_support_alert", "calculate_all_risks",
    "student", "risk_profile", "interventions_for_student",
    "coach_assignments_for_student", "tutoring_for_student", "indicators_for_student",
    "intervention_student",
]


def _rows(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, tuple(r))) for r in cur.fetchall()]
    finally:
        conn.close()


def all_student_ids() -> List[str]:
    return [r["student_id"] for r in _rows("SELECT student_id FROM students")]


def student_picker() -> List[Dict[str, Any]]:
    """Students for a chooser, ordered by surname."""
    return _rows("SELECT student_id, first_name, last_name FROM students "
                 "ORDER BY last_name, first_name")


def active_coaches() -> List[Dict[str, Any]]:
    # The table flags active coaches with ``is_active``; the old window
    # filtered on a ``status`` column that doesn't exist, so Assign Coach
    # always failed with "no such column".
    return _rows("SELECT coach_id, name FROM early_warning_coaches WHERE is_active = 1")


def coaches_with_load() -> List[Dict[str, Any]]:
    """Every coach with their count of active assignments."""
    return _rows('''
        SELECT c.coach_id, c.name, c.specialization, c.max_students,
               COUNT(ca.assignment_id) as current_students
        FROM early_warning_coaches c
        LEFT JOIN early_warning_coaching_assignments ca
            ON c.coach_id = ca.coach_id AND ca.status = 'active'
        GROUP BY c.coach_id
    ''')


def active_coach_assignments() -> List[Dict[str, Any]]:
    return _rows('''
        SELECT ca.*, s.first_name, s.last_name, c.name as coach_name
        FROM early_warning_coaching_assignments ca
        JOIN students s ON ca.student_id = s.student_id
        JOIN early_warning_coaches c ON ca.coach_id = c.coach_id
        WHERE ca.status = 'active'
        ORDER BY ca.assigned_date DESC
    ''')


def active_assignment_coach(student_id: str) -> Optional[int]:
    """The coach on a student's active assignment, if any."""
    rows = _rows('''
        SELECT coach_id FROM early_warning_coaching_assignments
        WHERE student_id = ? AND status = 'active'
    ''', (student_id,))
    return rows[0]["coach_id"] if rows else None


def tutoring_recommendations() -> List[Dict[str, Any]]:
    return _rows('''
        SELECT tr.*, s.first_name, s.last_name
        FROM early_warning_tutoring_recommendations tr
        JOIN students s ON tr.student_id = s.student_id
        ORDER BY tr.created_at DESC
    ''')


def risk_indicators(limit: int = 500) -> List[Dict[str, Any]]:
    return _rows('''
        SELECT i.*, s.first_name, s.last_name
        FROM early_warning_indicators i
        JOIN students s ON i.student_id = s.student_id
        ORDER BY i.detected_at DESC
        LIMIT ?
    ''', (int(limit),))


def send_support_alert(student_id: str) -> Tuple[str, bool]:
    """Email a student the 'support available' template.

    Returns ``(email, sent)``; ``sent`` is False when the email service
    isn't installed. Raises ``LookupError`` for an unknown student.
    """
    rows = _rows("SELECT email_address, first_name FROM students WHERE student_id = ?",
                 (student_id,))
    if not rows:
        raise LookupError("Student not found")
    email, name = rows[0]["email_address"], rows[0]["first_name"]
    try:
        from education_system.systems.university.infrastructure.email.email_service import send_email
        from education_system.systems.university.infrastructure.email.template_utils import render_template
    except ImportError:
        return email, False
    subject, body = render_template('student_support_available', {'name': name})
    send_email(email, subject, body)
    return email, True


def calculate_all_risks() -> int:
    """Recalculate every student's risk score; returns how many succeeded."""
    from education_system.systems.university.domains.student_support.domain.early_warning.early_warning_core import (
        RiskAssessmentManager,
    )
    count = 0
    for student_id in all_student_ids():
        try:
            RiskAssessmentManager.calculate_risk_score(student_id)
            count += 1
        except Exception:
            logger.exception("Error calculating risk for %s", student_id)
    return count


# ---------------------------------------------------------------------------
# One student — the Student Overview tab
# ---------------------------------------------------------------------------

def student(student_id: str) -> Optional[Dict[str, Any]]:
    rows = _rows("SELECT student_id, first_name, last_name, email_address, course, "
                 "program, year_of_study, status FROM students WHERE student_id = ?",
                 (student_id,))
    return rows[0] if rows else None


def risk_profile(student_id: str) -> Optional[Dict[str, Any]]:
    rows = _rows("SELECT * FROM early_warning_profiles WHERE student_id = ?", (student_id,))
    return rows[0] if rows else None


def interventions_for_student(student_id: str) -> List[Dict[str, Any]]:
    """Every intervention for a student, any status, newest first."""
    return _rows("SELECT * FROM early_warning_interventions WHERE student_id = ? "
                 "ORDER BY created_at DESC, intervention_id DESC", (student_id,))


def coach_assignments_for_student(student_id: str) -> List[Dict[str, Any]]:
    return _rows('''
        SELECT ca.*, c.name as coach_name
        FROM early_warning_coaching_assignments ca
        JOIN early_warning_coaches c ON ca.coach_id = c.coach_id
        WHERE ca.student_id = ?
        ORDER BY ca.assigned_date DESC
    ''', (student_id,))


def tutoring_for_student(student_id: str) -> List[Dict[str, Any]]:
    return _rows("SELECT * FROM early_warning_tutoring_recommendations WHERE student_id = ? "
                 "ORDER BY created_at DESC", (student_id,))


def indicators_for_student(student_id: str) -> List[Dict[str, Any]]:
    return _rows("SELECT * FROM early_warning_indicators WHERE student_id = ? "
                 "ORDER BY is_resolved, detected_at DESC", (student_id,))


def intervention_student(intervention_id: int) -> Optional[str]:
    """The student an intervention belongs to."""
    rows = _rows("SELECT student_id FROM early_warning_interventions WHERE intervention_id = ?",
                 (int(intervention_id),))
    return str(rows[0]["student_id"]) if rows else None
