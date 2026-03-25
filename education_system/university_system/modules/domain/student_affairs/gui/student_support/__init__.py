"""Student Support GUI Package"""
from education_system.university_system.modules.domain.student_affairs.gui.student_support.base import StudentSupportGUIBase
from education_system.university_system.modules.domain.student_affairs.gui.student_support.dashboard import DashboardMixin
from education_system.university_system.modules.domain.student_affairs.gui.student_support.search import SearchMixin
from education_system.university_system.modules.domain.student_affairs.gui.student_support.ticket_forms import TicketFormsMixin
from education_system.university_system.modules.domain.student_affairs.gui.student_support.ticket_detail import TicketDetailMixin
from education_system.university_system.modules.domain.student_affairs.gui.student_support.ticket_actions import TicketActionsMixin
from education_system.university_system.modules.domain.student_affairs.gui.student_support.content import ContentMixin
from education_system.university_system.modules.domain.student_affairs.gui.student_support.admin import AdminMixin
from education_system.university_system.modules.domain.student_affairs.gui.student_support.reports_export import ReportsExportMixin
from education_system.university_system.modules.domain.student_affairs.gui.student_support.launcher import launch_student_support_gui, SupportPortalLauncher
from education_system.university_system.modules.domain.student_affairs.gui.student_support.misc import MiscMixin


class StudentSupportGUI(
    StudentSupportGUIBase,
    DashboardMixin,
    SearchMixin,
    TicketFormsMixin,
    TicketDetailMixin,
    TicketActionsMixin,
    ContentMixin,
    AdminMixin,
    ReportsExportMixin,
    MiscMixin
):
    """Complete Student Support GUI combining all mixins."""
    pass


__all__ = [
    'StudentSupportGUI',
    'StudentSupportGUIBase',
    'DashboardMixin',
    'SearchMixin',
    'TicketFormsMixin',
    'TicketDetailMixin',
    'TicketActionsMixin',
    'ContentMixin',
    'AdminMixin',
    'ReportsExportMixin',
    'MiscMixin',
    'launch_student_support_gui',
    'SupportPortalLauncher',
]
