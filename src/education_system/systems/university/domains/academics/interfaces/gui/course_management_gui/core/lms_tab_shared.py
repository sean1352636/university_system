"""Shared imports and module state for the split implementation."""

from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.core._imports import (
    _, tk, ttk, messagebox, ScrolledText, sqlite3, DEFAULT_DB_PATH, datetime, json,
)

try:
    from education_system.systems.university.domains.academics.domain.services.lms.lms_core import (
        LMSCourseManager, LMSContentManager, LMSDiscussionManager,
        LMSQuizManager, LMSGradebookManager,
    )
    from education_system.systems.university.domains.academics.domain.services.lms.db_schema import initialize_lms_database
    from education_system.systems.university.infrastructure.database.db import get_connection
    LMS_AVAILABLE = True
except ImportError:
    LMS_AVAILABLE = False

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
except ImportError:
    def log_activity(*a, **kw): pass

try:
    from education_system.platform.features.lms.course_content_service import CourseContentService
    from education_system.platform.features.lms.learning_progress_service import LearningProgressService
    from education_system.platform.features.lms.quiz_service import QuizService
    from education_system.platform.features.lms.resource_library_service import ResourceLibraryService
    from education_system.platform.features.lms.schema import create_lms_tables
    SHARED_LMS_AVAILABLE = True
except ImportError:
    SHARED_LMS_AVAILABLE = False

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
