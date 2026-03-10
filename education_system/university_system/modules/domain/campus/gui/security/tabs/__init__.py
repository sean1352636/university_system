"""Tab mixin classes for the Campus Public Safety Management System."""

from ._base import BaseMixin
from .dashboard import DashboardMixin
from .cases import CasesMixin
from .officers import OfficersMixin
from .complaints import ComplaintsMixin
from .patrol_logs import PatrolLogsMixin
from .criminals import CriminalsMixin
from .evidence import EvidenceMixin
from .reports import ReportsMixin

__all__ = [
    'BaseMixin', 'DashboardMixin', 'CasesMixin', 'OfficersMixin',
    'ComplaintsMixin', 'PatrolLogsMixin', 'CriminalsMixin',
    'EvidenceMixin', 'ReportsMixin',
]
