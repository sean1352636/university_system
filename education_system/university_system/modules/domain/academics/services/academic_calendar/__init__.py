"""
Academic Calendar Service Package

This package was refactored from a single 7,011-line file into modular components.
All public classes and functions are re-exported here for backward compatibility.

Existing imports like:
    from education_system.university_system.modules.domain.academics.services.academic_calendar import (
        AcademicCalendarManager, CalendarConfig, display_academic_calendar_menu, ...
    )
will continue to work without changes.
"""

# Exception classes
from .exceptions import (
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
from .config import (
    CalendarConfig,
    ValidationUtils,
    SecurityUtils,
)

# Database layer
from .database import (
    DatabaseManager,
    DatabaseTransaction,
)

# Authentication
from .auth import AuthenticationManager

# Manager classes
from .recurring_events import RecurringEventManager
from .dependencies import EventDependencyManager
from .reporting import AdvancedReportingManager
from .notifications import SMSNotificationManager, NotificationManager
from .mobile_api import MobileAPIManager
from .categories import EventCategoryManager, CourseManager
from .resources import ResourceManager
from .visualization import (
    EnhancedCalendarVisualizationManager,
    DataVisualizationManager,
)
from .deadlines import AcademicDeadlineManager
from .batch import BatchOperationsManager
from .timezone import EnhancedTimeZoneManager
from .search import AdvancedSearchManager
from .audit import AuditManager
from .holidays import HolidayManager

# Main orchestrator
from .calendar_core import AcademicCalendarManager

# Web API
from .web_api import CalendarWebAPI

# Factory function
from .factory import create_calendar_manager

# CLI functions and global auth
from .cli import (
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
    'display_calendar_data',
    'display_events_list',
    'ensure_calendar_permissions',
    'fix_calendar_database',
]
