"""Tab mixin classes for the Campus Public Safety Management System."""

from education_system.systems.university.domains.operations.interfaces.gui.campus.security.tabs._base import BaseMixin
from education_system.systems.university.domains.operations.interfaces.gui.campus.security.tabs.dashboard import DashboardMixin
from education_system.systems.university.domains.operations.interfaces.gui.campus.security.tabs.cases import CasesMixin
from education_system.systems.university.domains.operations.interfaces.gui.campus.security.tabs.officers import OfficersMixin
from education_system.systems.university.domains.operations.interfaces.gui.campus.security.tabs.complaints import ComplaintsMixin
from education_system.systems.university.domains.operations.interfaces.gui.campus.security.tabs.patrol_logs import PatrolLogsMixin
from education_system.systems.university.domains.operations.interfaces.gui.campus.security.tabs.criminals import CriminalsMixin
from education_system.systems.university.domains.operations.interfaces.gui.campus.security.tabs.evidence import EvidenceMixin
from education_system.systems.university.domains.operations.interfaces.gui.campus.security.tabs.reports import ReportsMixin

__all__ = [
    'BaseMixin', 'DashboardMixin', 'CasesMixin', 'OfficersMixin',
    'ComplaintsMixin', 'PatrolLogsMixin', 'CriminalsMixin',
    'EvidenceMixin', 'ReportsMixin',
]
