"""Assignment System GUI Module

Modular assignment and assessment management system with separate manager classes
for different functionality areas.
"""

from education_system.university_system.modules.domain.academics.gui.assignment_system.assignment_gui import AssignmentGUI, launch_gui, display_assignment_menu_gui, display_assignment_menu
from education_system.university_system.modules.domain.academics.gui.assignment_system.db_manager import DatabaseManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.layout_manager import LayoutManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.dashboard import DashboardManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.assignment_manager import AssignmentManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.submission_manager import SubmissionManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.template_manager import TemplateManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.extension_manager import ExtensionManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.grading_manager import GradingManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.group_manager import GroupManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.messaging import MessagingManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.notifications import NotificationManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.analytics import AnalyticsManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.file_preview import FilePreviewManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.assessment_manager import AssessmentManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.rubric_manager import RubricManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.peer_review import PeerReviewManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.maintenance import MaintenanceManager

__all__ = [
    'AssignmentGUI',
    'launch_gui',
    'display_assignment_menu_gui',
    'display_assignment_menu',
    'DatabaseManager',
    'LayoutManager',
    'DashboardManager',
    'AssignmentManager',
    'SubmissionManager',
    'TemplateManager',
    'ExtensionManager',
    'GradingManager',
    'GroupManager',
    'MessagingManager',
    'NotificationManager',
    'AnalyticsManager',
    'FilePreviewManager',
    'AssessmentManager',
    'RubricManager',
    'PeerReviewManager',
    'MaintenanceManager',
]
