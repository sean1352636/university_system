"""
Academic Calendar Service Package

This package was refactored from a single 7,011-line file into modular components.
All public classes and functions are re-exported here for backward compatibility.

Existing imports like:
    from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar import (
        AcademicCalendarManager, CalendarConfig, display_academic_calendar_menu, ...
    )
will continue to work without changes.
"""

# Exception classes
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.exceptions import (
    CalendarError,
    ValidationError,
    DatabaseError,
    AuthenticationError,
    PermissionError,
    ExportError,
    SyncError,
    CalendarExceptionHandler,
)

# Configuration and utilities
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.config import (
    CalendarConfig,
    ValidationUtils,
    SecurityUtils,
)

# Database layer
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.database import (
    DatabaseManager,
    DatabaseTransaction,
)

# Authentication
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.auth import AuthenticationManager

# Manager classes
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.recurring_events import RecurringEventManager
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.dependencies import EventDependencyManager
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.reporting import AdvancedReportingManager
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.notifications import SMSNotificationManager, NotificationManager
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.mobile_api import MobileAPIManager
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.categories import EventCategoryManager, CourseManager
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.resources import ResourceManager
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.visualization import (
    EnhancedCalendarVisualizationManager,
    DataVisualizationManager,
)
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.deadlines import AcademicDeadlineManager
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.batch import BatchOperationsManager
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.timezone import EnhancedTimeZoneManager
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.search import AdvancedSearchManager
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.audit import AuditManager
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.holidays import HolidayManager

# Main orchestrator
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.calendar_core import AcademicCalendarManager

# Web API
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.web_api import CalendarWebAPI

# Factory function
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.factory import create_calendar_manager

# CLI functions and global auth
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.cli import (
    auth,
    set_auth,
    display_academic_calendar_menu,
    handle_create_trip_event,
    handle_view_trip_calendar_links,
    handle_add_event,
    handle_update_event,
    handle_delete_event,
    handle_add_academic_year,
    handle_add_semester,
    handle_view_calendar,
    handle_search_events,
    handle_export_calendar,
    handle_create_recurring_event,
    handle_project_milestones,
    handle_event_dependencies,
    handle_bulk_operations,
    handle_advanced_reports,
    handle_visualizations,
    handle_system_management,
    handle_import_calendar,
    handle_restore_database,
    display_calendar_data,
    display_events_list,
    ensure_calendar_permissions,
    fix_calendar_database,
)

__all__ = [
    # Exceptions
    'CalendarError',
    'ValidationError',
    'DatabaseError',
    'AuthenticationError',
    'PermissionError',
    'ExportError',
    'SyncError',
    'CalendarExceptionHandler',
    # Config & Utils
    'CalendarConfig',
    'ValidationUtils',
    'SecurityUtils',
    # Database
    'DatabaseManager',
    'DatabaseTransaction',
    # Auth
    'AuthenticationManager',
    # Managers
    'RecurringEventManager',
    'EventDependencyManager',
    'AdvancedReportingManager',
    'SMSNotificationManager',
    'NotificationManager',
    'MobileAPIManager',
    'EventCategoryManager',
    'CourseManager',
    'ResourceManager',
    'EnhancedCalendarVisualizationManager',
    'DataVisualizationManager',
    'AcademicDeadlineManager',
    'BatchOperationsManager',
    'EnhancedTimeZoneManager',
    'AdvancedSearchManager',
    'AuditManager',
    'HolidayManager',
    # Main
    'AcademicCalendarManager',
    'CalendarWebAPI',
    'create_calendar_manager',
    # CLI
    'auth',
    'set_auth',
    'display_academic_calendar_menu',
    'handle_create_trip_event',
    'handle_view_trip_calendar_links',
    'handle_add_event',
    'handle_update_event',
    'handle_delete_event',
    'handle_add_academic_year',
    'handle_add_semester',
    'handle_view_calendar',
    'handle_search_events',
    'handle_export_calendar',
    'handle_create_recurring_event',
    'handle_project_milestones',
    'handle_event_dependencies',
    'handle_bulk_operations',
    'handle_advanced_reports',
    'handle_visualizations',
    'handle_system_management',
    'handle_import_calendar',
    'handle_restore_database',
    'display_calendar_data',
    'display_events_list',
    'ensure_calendar_permissions',
    'fix_calendar_database',
]
