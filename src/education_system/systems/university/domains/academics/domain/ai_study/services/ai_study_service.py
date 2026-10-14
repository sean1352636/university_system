"""Moved into the Study Hub.

``ai_study`` was merged with the other two study features because they
shared ``study_profiles`` without agreeing on it — see
``study_hub/services/profiles.py``. The implementation now lives at
``study_hub.services.planning``; this re-export keeps existing imports
(CLI, API routes, the event bus and tests) working.
"""

from education_system.systems.university.domains.academics.domain.study_hub.services.planning import (  # noqa: F401
    AIStudyService,
)

__all__ = ["AIStudyService"]
