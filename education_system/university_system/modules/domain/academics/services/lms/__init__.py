"""
LMS (Learning Management System) Service Module

This module provides comprehensive LMS functionality including course management,
content delivery, quizzes, discussions, and gradebook integration.
"""

from .lms_core import (
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
