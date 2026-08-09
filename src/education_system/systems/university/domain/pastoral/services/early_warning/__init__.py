"""
Student Success Early Warning System Service Module

This module provides at-risk student identification, automated interventions,
success coaching, progress monitoring, and tutoring recommendations.
"""

from education_system.systems.university.domain.pastoral.services.early_warning.early_warning_core import (
    RiskAssessmentManager,
    IndicatorManager,
    InterventionManager,
    CoachingManager,
    TutoringManager,
)

__all__ = [
    'RiskAssessmentManager',
    'IndicatorManager',
    'InterventionManager',
    'CoachingManager',
    'TutoringManager',
]
