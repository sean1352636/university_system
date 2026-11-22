"""Assessment QA hooks shared by the assignment GUI screens.

Kept free of heavy imports so any screen can use it: anonymised marker
labels, and running a saved mark through the QA rules.
"""
import logging

from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def _qa_service():
    from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa import (
        AssessmentQAService,
    )
    return AssessmentQAService(str(DEFAULT_DB_PATH))


def _marker_label(submission_id, student_name):
    """Student name, or a candidate number while the assignment is marked anonymously."""
    try:
        return _qa_service().marker_label_for_submission(submission_id, student_name)
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
        return student_name


def _marker_labels(rows):
    try:
        return _qa_service().marker_labels(rows)
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
        return dict(rows)


def _apply_qa_rules(submission_id, percentage, marker_id, feedback):
    """Pass a saved mark through word-limit, referral-cap and release rules."""
    from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa import (
        apply_mark_rules,
    )
    return apply_mark_rules(submission_id, percentage, marker=marker_id, feedback=feedback,
                            db_path=str(DEFAULT_DB_PATH))


def _qa_note(result):
    from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa import (
        mark_note,
    )
    note = mark_note(result)
    return f"\n\n{note}" if note else ""
