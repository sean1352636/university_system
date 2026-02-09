"""Assignment System GUI Module

Modular assignment and assessment management system with separate manager classes
for different functionality areas.
"""

from university_system.modules.domain.academics.gui.assignment_system.assignment_gui import AssignmentGUI, launch_gui, display_assignment_menu_gui, display_assignment_menu
from university_system.modules.domain.academics.gui.assignment_system.db_manager import DatabaseManager
from university_system.modules.domain.academics.gui.assignment_system.layout_manager import LayoutManager
from university_system.modules.domain.academics.gui.assignment_system.dashboard import DashboardManager
from university_system.modules.domain.academics.gui.assignment_system.assignment_manager import AssignmentManager
from university_system.modules.domain.academics.gui.assignment_system.submission_manager import SubmissionManager
from university_system.modules.domain.academics.gui.assignment_system.template_manager import TemplateManager
from university_system.modules.domain.academics.gui.assignment_system.extension_manager import ExtensionManager
from university_system.modules.domain.academics.gui.assignment_system.grading_manager import GradingManager
from university_system.modules.domain.academics.gui.assignment_system.group_manager import GroupManager
from university_system.modules.domain.academics.gui.assignment_system.messaging import MessagingManager
from university_system.modules.domain.academics.gui.assignment_system.notifications import NotificationManager
from university_system.modules.domain.academics.gui.assignment_system.analytics import AnalyticsManager
from university_system.modules.domain.academics.gui.assignment_system.file_preview import FilePreviewManager
from university_system.modules.domain.academics.gui.assignment_system.assessment_manager import AssessmentManager
from university_system.modules.domain.academics.gui.assignment_system.rubric_manager import RubricManager
from university_system.modules.domain.academics.gui.assignment_system.peer_review import PeerReviewManager
from university_system.modules.domain.academics.gui.assignment_system.maintenance import MaintenanceManager

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
