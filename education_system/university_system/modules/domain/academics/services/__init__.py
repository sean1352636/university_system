"""
Academic Services Package

Provides academic services including:
- Virtual classroom management
- Course evaluation
- Learning Management System (LMS)
- Plagiarism detection
- Assignment management
- Degree audit
- Attendance tracking
- Timetable management
- Parent portal
"""

# Import parent portal
try:
    from education_system.university_system.modules.domain.academics.services.parent_portal import (
        ParentPortal,
    )
    PARENT_PORTAL_AVAILABLE = True
except ImportError:
    ParentPortal = None
    PARENT_PORTAL_AVAILABLE = False

__all__ = [
    'ParentPortal',
    'PARENT_PORTAL_AVAILABLE',
]
