"""Legal services adapter — open a case for academic-integrity events.

Calls ``legal_services_core.CaseManager.create_case`` so an integrity
log row also generates a tracked legal case in
``legal_cases``. Failures are logged and swallowed — the integrity
log row is still authoritative on the academics side.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def open_integrity_case(
    *,
    student_id: str,
    student_name: str,
    student_email: str,
    assessment_title: str,
    event_type: str,
    details: str = "",
    created_by: str | None = None,
    priority: str = "normal",
) -> int | None:
    """Create a legal case for an academic-integrity event.

    Returns the new ``case_id`` or ``None`` on failure / when the
    legal services module is unavailable.
    """
    try:
        from education_system.post_18.university_system.modules.domain.operations.legal.services.legal_services_core import (
            CaseManager,
        )
    except ImportError as exc:
        logger.debug("legal_services_core not available: %s", exc)
        return None

    try:
        return CaseManager.create_case(
            client_id=str(student_id),
            client_name=student_name,
            client_email=student_email,
            case_type="academic_integrity",
            case_title=f"Integrity event — {assessment_title} ({event_type})",
            case_description=details,
            priority=priority,
            created_by=created_by,
        )
    except Exception as exc:
        logger.warning("open_integrity_case failed for %s: %s", student_id, exc)
        return None
