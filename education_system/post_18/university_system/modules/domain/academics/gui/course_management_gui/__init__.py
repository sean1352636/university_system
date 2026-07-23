# course_management_gui package
# Main GUI class
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.core.main_gui import CourseManagementGUI

# Core dialogs
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.core.validation import CourseValidationDialog

# Analytics dialogs
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.analytics.analytics import CourseAnalyticsDialog, EnrollmentReportDialog

# Search dialogs
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.search.search import AdvancedCourseSearchDialog, AdvancedSearchDialog

# Schedule dialogs
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.schedules.schedules import (
    CreateScheduleDialog,
    ViewSchedulesDialog,
    UpdateScheduleDialog,
    UpdateScheduleFormDialog,
)

# Course dialogs
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.courses.course_crud import CourseCreateDialog, CourseEditDialog
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.courses.course_status import ManageCourseStatusDialog, CourseHistoryDialog

# Prerequisites dialogs
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.prerequisites.prerequisites import (
    PrerequisitesWindow,
    AddPrerequisiteDialog,
    RemovePrerequisiteDialog,
)

# Waitlist dialogs
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.waitlists import (
    AddToWaitlistDialog,
    ViewWaitlistsDialog,
    ProcessWaitlistDialog,
)

# Recommendation dialogs
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.recommendations import (
    RecommendCoursesDialog,
    AlternativeCourseDialog,
    RecommendationsDialog,
)

# Bulk operations
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.bulk.bulk_operations import BulkUpdateDialog

# Import/Export dialogs
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.import_export.import_export import ImportExportDialog

# Instructor dialogs
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.instructors.instructors import InstructorCreateDialog, AssignInstructorDialog, InstructorDetailsDialog

# Maintenance dialogs
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.maintenance.maintenance import MaintenanceDialog

# Wrappers for backwards compatibility
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.wrappers.compatibility import BackwardsCompatibilityWrapper

# CLI entry points
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.cli.entry_points import (
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
    "InstructorDetailsDialog",
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
