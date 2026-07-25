"""Shared Learning Management System (LMS) foundation module.

Provides course content management, learning progress tracking, quiz
functionality, discussion forums, gradebook, course management, and a
resource library that all 4 education subsystems can integrate into
their own databases.
"""

from education_system.platform.features.lms.schema import create_lms_tables
from education_system.platform.features.lms.course_content_service import CourseContentService
from education_system.platform.features.lms.learning_progress_service import LearningProgressService
from education_system.platform.features.lms.quiz_service import QuizService
from education_system.platform.features.lms.resource_library_service import ResourceLibraryService
from education_system.platform.features.lms.discussion_service import DiscussionService
from education_system.platform.features.lms.gradebook_service import GradebookService
from education_system.platform.features.lms.course_management_service import CourseManagementService

__all__ = [
    "create_lms_tables",
    "CourseContentService",
    "LearningProgressService",
    "QuizService",
    "ResourceLibraryService",
    "DiscussionService",
    "GradebookService",
    "CourseManagementService",
]
