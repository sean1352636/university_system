"""Tab mixin classes for the Campus Public Safety Management System."""

from education_system.post_18.university_system.modules.domain.campus.gui.security.tabs._base import BaseMixin
from education_system.post_18.university_system.modules.domain.campus.gui.security.tabs.dashboard import DashboardMixin
from education_system.post_18.university_system.modules.domain.campus.gui.security.tabs.cases import CasesMixin
from education_system.post_18.university_system.modules.domain.campus.gui.security.tabs.officers import OfficersMixin
from education_system.post_18.university_system.modules.domain.campus.gui.security.tabs.complaints import ComplaintsMixin
from education_system.post_18.university_system.modules.domain.campus.gui.security.tabs.patrol_logs import PatrolLogsMixin
from education_system.post_18.university_system.modules.domain.campus.gui.security.tabs.criminals import CriminalsMixin
from education_system.post_18.university_system.modules.domain.campus.gui.security.tabs.evidence import EvidenceMixin
from education_system.post_18.university_system.modules.domain.campus.gui.security.tabs.reports import ReportsMixin

__all__ = [
    'BaseMixin', 'DashboardMixin', 'CasesMixin', 'OfficersMixin',
    'ComplaintsMixin', 'PatrolLogsMixin', 'CriminalsMixin',
    'EvidenceMixin', 'ReportsMixin',
]
