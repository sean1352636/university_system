"""Student Support GUI Package"""
from .base import StudentSupportGUIBase
from .dashboard import DashboardMixin
from .search import SearchMixin
from .ticket_forms import TicketFormsMixin
from .ticket_detail import TicketDetailMixin
from .ticket_actions import TicketActionsMixin
from .content import ContentMixin
from .admin import AdminMixin
from .reports_export import ReportsExportMixin
from .launcher import launch_student_support_gui, SupportPortalLauncher
from .misc import MiscMixin


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
