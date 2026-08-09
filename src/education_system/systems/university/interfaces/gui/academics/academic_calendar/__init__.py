# Re-export all classes and functions

# Exceptions
from education_system.systems.university.interfaces.gui.academics.academic_calendar.exceptions import (
    CalendarError,
    ValidationError,
    DatabaseError,
    AuthenticationError,
    PermissionError,
    ExportError,
    SyncError,
)

# Validators
from education_system.systems.university.interfaces.gui.academics.academic_calendar.validators import (
    validate_date,
    validate_datetime,
    validate_email,
    validate_uuid,
    sanitize_string,
)

# Security
from education_system.systems.university.interfaces.gui.academics.academic_calendar.security import (
    hash_password,
    verify_password,
    generate_token,
)

# Database
from education_system.systems.university.interfaces.gui.academics.academic_calendar.database import (
    ConnectionPool,
    DatabaseManager,
    init_calendar_database,
)

# Managers
from education_system.systems.university.interfaces.gui.academics.academic_calendar.managers import (
    RecurringEventManager,
    EventDependencyManager,
)

# Reporting
from education_system.systems.university.interfaces.gui.academics.academic_calendar.reporting import ReportingEngine

# Notifications
from education_system.systems.university.interfaces.gui.academics.academic_calendar.notifications import NotificationManager

# Utils
from education_system.systems.university.interfaces.gui.academics.academic_calendar.utils import (
    handle_exception,
    log_and_suppress,
    convert_to_user_error,
    safe_grab_set,
    safe_show_error,
)

# Main GUI
from education_system.systems.university.interfaces.gui.academics.academic_calendar.main_gui import (
    CalendarGUI,
    launch_calendar_gui,
    run_gui_calendar,
    display_academic_calendar_gui,
    integrate_with_main_system,
)

# View Mixins
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dashboard import DashboardMixin
from education_system.systems.university.interfaces.gui.academics.academic_calendar.calendar_view import CalendarViewMixin
from education_system.systems.university.interfaces.gui.academics.academic_calendar.events_view import EventsViewMixin
from education_system.systems.university.interfaces.gui.academics.academic_calendar.academic_view import AcademicViewMixin
from education_system.systems.university.interfaces.gui.academics.academic_calendar.menu_actions import MenuActionsMixin

# Event Dialogs
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_event import (
    AddEventDialog,
    EditEventDialog,
    EventDetailsDialog,
)

# Recurring Event Dialogs
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_recurring import (
    RecurringEventDialog,
    RecurringEventsDialog,
)

# Academic Dialogs
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_academic import (
    AddAcademicYearDialog,
    AddSemesterDialog,
)

# Admin Dialogs
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_admin import (
    SystemMaintenanceDialog,
    AuditLogsDialog,
    AuditDetailsDialog,
    SettingsDialog,
    TimezoneSettingsDialog,
)

# Resource Dialogs
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_resources import (
    ResourceManagementDialog,
    AddResourceDialog,
    BookResourceDialog,
    CourseManagementDialog,
    AddCourseDialog,
)

# Category Dialogs
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_categories import (
    EventCategoriesDialog,
    AddCategoryDialog,
    AddTagDialog,
    AssignTagDialog,
)

# Report Dialogs
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_reports import (
    ReportsDialog,
    ReportViewDialog,
    DataVisualizationDialog,
    ProjectMilestonesDialog,
    AddMilestoneDialog,
)

# Search Dialogs
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_search import AdvancedSearchDialog

# Misc Dialogs
from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_misc import (
    ExportDialog,
    ImportCalendarDialog,
    CalendarSyncDialog,
    ImportHolidaysDialog,
    BulkOperationsDialog,
)

# Misc functions (launcher aliases)
from education_system.systems.university.interfaces.gui.academics.academic_calendar.misc import (
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
    'ExportError',
    'SyncError',
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
