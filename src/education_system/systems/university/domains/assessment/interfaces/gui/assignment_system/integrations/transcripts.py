"""Gradebook / transcript adapter — the bridge now lives in the domain layer.

Kept so the assignment GUI's ``integrations`` package keeps exporting
``sync_grade_to_gradebook``; see ``assessment_qa.gradebook``.
"""

from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa.gradebook import (  # noqa: F401
    sync_grade_to_gradebook,
)
