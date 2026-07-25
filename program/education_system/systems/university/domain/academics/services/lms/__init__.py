"""
LMS (Learning Management System) Service Module

This module provides comprehensive LMS functionality including course management,
content delivery, quizzes, discussions, and gradebook integration.
"""

from education_system.systems.university.domain.academics.services.lms.lms_core import (
    LMSCourseManager,
    LMSContentManager,
    LMSDiscussionManager,
    LMSQuizManager,
    LMSGradebookManager,
)

__all__ = [
    'LMSCourseManager',
    'LMSContentManager',
    'LMSDiscussionManager',
    'LMSQuizManager',
    'LMSGradebookManager',
]
