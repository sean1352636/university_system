"""Heuristic auto-grading for text submissions.

Pure-logic module, no UI and no external API. Use ``score_submission``
to produce a suggested grade + breakdown for a single submission;
``grade_submission_by_id`` is a convenience wrapper that pulls the
submission, assignment, rubric, and file off the database before
scoring.
"""

from education_system.post_18.university_system.modules.domain.academics.services.ai_grading.auto_grader import (
    AutoGradingResult,
    CriterionResult,
    grade_submission_by_id,
    score_submission,
)

__all__ = [
    "AutoGradingResult",
    "CriterionResult",
    "score_submission",
    "grade_submission_by_id",
]
