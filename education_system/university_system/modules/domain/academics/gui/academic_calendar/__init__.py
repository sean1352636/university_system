# Re-export all classes and functions

# Exceptions
from .exceptions import (
    CalendarError,
    ValidationError,
    DatabaseError,
    AuthenticationError,
    PermissionError,
)

# Validators
from .validators import (
    validate_date,
    validate_datetime,
    validate_email,
    validate_uuid,
    sanitize_string,
)

# Security
from .security import (
    hash_password,
    verify_password,
    generate_token,
)

# Database
from .database import (
    ConnectionPool,
    DatabaseManager,
    init_calendar_database,
)

# Managers
from .managers import (
    RecurringEventManager,
    EventDependencyManager,
)

# Reporting
from .reporting import ReportingEngine

# Notifications
from .notifications import NotificationManager

# Utils
from .utils import (
    handle_exception,
    log_and_suppress,
    convert_to_user_error,
    safe_grab_set,
    safe_show_error,
)

# Main GUI
from .main_gui import (
    CalendarGUI,
    launch_calendar_gui,
    run_gui_calendar,
    display_academic_calendar_gui,
    integrate_with_main_system,
)

# View Mixins
from .dashboard import DashboardMixin
from .calendar_view import CalendarViewMixin
from .events_view import EventsViewMixin
from .academic_view import AcademicViewMixin
from .menu_actions import MenuActionsMixin

# Event Dialogs
from .dialogs_event import (
    AddEventDialog,
    EditEventDialog,
    EventDetailsDialog,
)

# Recurring Event Dialogs
from .dialogs_recurring import (
    RecurringEventDialog,
    RecurringEventsDialog,
)

# Academic Dialogs
from .dialogs_academic import (
    AddAcademicYearDialog,
    AddSemesterDialog,
)

# Admin Dialogs
from .dialogs_admin import (
    SystemMaintenanceDialog,
    AuditLogsDialog,
    AuditDetailsDialog,
    SettingsDialog,
    TimezoneSettingsDialog,
)

# Resource Dialogs
from .dialogs_resources import (
    ResourceManagementDialog,
    AddResourceDialog,
    BookResourceDialog,
    CourseManagementDialog,
    AddCourseDialog,
)

# Category Dialogs
from .dialogs_categories import (
    EventCategoriesDialog,
    AddCategoryDialog,
    AddTagDialog,
    AssignTagDialog,
)

# Report Dialogs
from .dialogs_reports import (
    ReportsDialog,
    ReportViewDialog,
    DataVisualizationDialog,
    ProjectMilestonesDialog,
    AddMilestoneDialog,
)

# Search Dialogs
from .dialogs_search import AdvancedSearchDialog

# Misc Dialogs
from .dialogs_misc import (
    ExportDialog,
    ImportCalendarDialog,
    CalendarSyncDialog,
    ImportHolidaysDialog,
    BulkOperationsDialog,
)

# Misc functions (launcher aliases)
from .misc import (
    launch_calendar_gui as misc_launch_calendar_gui,
    run_gui_calendar as misc_run_gui_calendar,
    display_academic_calendar_gui as misc_display_academic_calendar_gui,
    integrate_with_main_system as misc_integrate_with_main_system,
)

__all__ = [
    # Exceptions
    'CalendarError',
    'ValidationError',
    'DatabaseError',
    'AuthenticationError',
    'PermissionError',
    # Validators
    'validate_date',
    'validate_datetime',
    'validate_email',
    'validate_uuid',
    'sanitize_string',
    # Security
    'hash_password',
    'verify_password',
    'generate_token',
    # Database
    'ConnectionPool',
    'DatabaseManager',
    'init_calendar_database',
    # Managers
    'RecurringEventManager',
    'EventDependencyManager',
    # Reporting & Notifications
    'ReportingEngine',
    'NotificationManager',
    # Utils
    'handle_exception',
    'log_and_suppress',
    'convert_to_user_error',
    'safe_grab_set',
    'safe_show_error',
    # Main GUI
    'CalendarGUI',
    'launch_calendar_gui',
    'run_gui_calendar',
    'display_academic_calendar_gui',
    'integrate_with_main_system',
    # View Mixins
    'DashboardMixin',
    'CalendarViewMixin',
    'EventsViewMixin',
    'AcademicViewMixin',
    'MenuActionsMixin',
    # Dialogs
    'AddEventDialog',
    'EditEventDialog',
    'EventDetailsDialog',
    'RecurringEventDialog',
    'RecurringEventsDialog',
    'AddAcademicYearDialog',
    'AddSemesterDialog',
    'SystemMaintenanceDialog',
    'AuditLogsDialog',
    'AuditDetailsDialog',
    'SettingsDialog',
    'TimezoneSettingsDialog',
    'ResourceManagementDialog',
    'AddResourceDialog',
    'BookResourceDialog',
    'CourseManagementDialog',
    'AddCourseDialog',
    'EventCategoriesDialog',
    'AddCategoryDialog',
    'AddTagDialog',
    'AssignTagDialog',
    'ReportsDialog',
    'ReportViewDialog',
    'DataVisualizationDialog',
    'ProjectMilestonesDialog',
    'AddMilestoneDialog',
    'AdvancedSearchDialog',
    'ExportDialog',
    'ImportCalendarDialog',
    'CalendarSyncDialog',
    'ImportHolidaysDialog',
    'BulkOperationsDialog',
]
