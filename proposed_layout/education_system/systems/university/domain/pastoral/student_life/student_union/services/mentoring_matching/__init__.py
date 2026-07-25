"""Mentoring matching sub-package — additive layer over the existing mentorship module.

Provides a structured matching algorithm and outcome capture without modifying
existing tables (mentorship_relationships / mentorship_sessions / mentorship_ratings).
"""
from .matching_service import MentoringMatchingService, MentoringMatchingError

__all__ = ["MentoringMatchingService", "MentoringMatchingError"]
