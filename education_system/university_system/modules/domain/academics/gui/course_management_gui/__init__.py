# course_management_gui package
# Main GUI class
from .core.main_gui import CourseManagementGUI

# Core dialogs
from .core.validation import CourseValidationDialog

# Analytics dialogs
from .analytics.analytics import CourseAnalyticsDialog, EnrollmentReportDialog

# Search dialogs
from .search.search import AdvancedCourseSearchDialog, AdvancedSearchDialog

# Schedule dialogs
from .schedules.schedules import (
    CreateScheduleDialog,
    ViewSchedulesDialog,
    UpdateScheduleDialog,
    UpdateScheduleFormDialog,
)

# Course dialogs
from .courses.course_crud import CourseCreateDialog, CourseEditDialog
from .courses.course_status import ManageCourseStatusDialog, CourseHistoryDialog

# Prerequisites dialogs
from .prerequisites.prerequisites import (
    PrerequisitesWindow,
    AddPrerequisiteDialog,
    RemovePrerequisiteDialog,
)

# Waitlist dialogs
from .waitlists.waitlists import (
    AddToWaitlistDialog,
    ViewWaitlistsDialog,
    ProcessWaitlistDialog,
)

# Recommendation dialogs
from .recommendations.recommendations import (
    RecommendCoursesDialog,
    AlternativeCourseDialog,
    RecommendationsDialog,
)

# Bulk operations
from .bulk.bulk_operations import BulkUpdateDialog

# Import/Export dialogs
from .import_export.import_export import ImportExportDialog

# Instructor dialogs
from .instructors.instructors import InstructorCreateDialog, AssignInstructorDialog

# Maintenance dialogs
from .maintenance.maintenance import MaintenanceDialog

# Wrappers for backwards compatibility
from .wrappers.compatibility import BackwardsCompatibilityWrapper

# CLI entry points
from .cli.entry_points import (
    run_gui_application,
    cli_interface,
    init_gui_mode,
    show_gui,
    create_course_gui,
    view_courses_gui,
    search_courses_gui,
    analytics_gui,
    print_usage,
)

__all__ = [
    # Main class
    "CourseManagementGUI",
    # Core
    "CourseValidationDialog",
    # Analytics
    "CourseAnalyticsDialog",
    "EnrollmentReportDialog",
    # Search
    "AdvancedCourseSearchDialog",
    "AdvancedSearchDialog",
    # Schedules
    "CreateScheduleDialog",
    "ViewSchedulesDialog",
    "UpdateScheduleDialog",
    "UpdateScheduleFormDialog",
    # Courses
    "CourseCreateDialog",
    "CourseEditDialog",
    "ManageCourseStatusDialog",
    "CourseHistoryDialog",
    # Prerequisites
    "PrerequisitesWindow",
    "AddPrerequisiteDialog",
    "RemovePrerequisiteDialog",
    # Waitlists
    "AddToWaitlistDialog",
    "ViewWaitlistsDialog",
    "ProcessWaitlistDialog",
    # Recommendations
    "RecommendCoursesDialog",
    "AlternativeCourseDialog",
    "RecommendationsDialog",
    # Bulk
    "BulkUpdateDialog",
    # Import/Export
    "ImportExportDialog",
    # Instructors
    "InstructorCreateDialog",
    "AssignInstructorDialog",
    # Maintenance
    "MaintenanceDialog",
    # Wrappers
    "BackwardsCompatibilityWrapper",
    # CLI functions
    "run_gui_application",
    "cli_interface",
    "init_gui_mode",
    "show_gui",
    "create_course_gui",
    "view_courses_gui",
    "search_courses_gui",
    "analytics_gui",
    "print_usage",
]
