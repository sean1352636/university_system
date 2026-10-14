"""Study Hub — planning, practice, recommendations and study partners.

Merged from three separate features (``ai_study``, ``study_matching``,
``study_recommendations``) that shared a table without agreeing on it.
See ``services/profiles.py`` for what that cost.

The three capabilities are still distinct and still have their own
services; what they now share is the student's profile and their record
of time studied, which is what they were fighting over.
"""

from education_system.systems.university.domains.academics.domain.study_hub.services import (
    ProfileService, SessionService, STUDY_STYLES, normalise_style,
    AIStudyService, StudyMatchingService, StudyRecommendationService,
)

__all__ = [
    "ProfileService", "SessionService", "STUDY_STYLES", "normalise_style",
    "AIStudyService", "StudyMatchingService", "StudyRecommendationService",
]
