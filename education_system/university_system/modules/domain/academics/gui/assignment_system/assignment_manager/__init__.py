"""Assignment manager package - split from monolithic assignment_manager.py

Composes all mixin classes into a single AssignmentManager class via multiple inheritance.
"""

from education_system.university_system.modules.domain.academics.gui.assignment_system.assignment_manager._base import AssignmentManagerBase
from education_system.university_system.modules.domain.academics.gui.assignment_system.assignment_manager.student_views import StudentViewsMixin
from education_system.university_system.modules.domain.academics.gui.assignment_system.assignment_manager.admin_views import AdminViewsMixin
from education_system.university_system.modules.domain.academics.gui.assignment_system.assignment_manager.management import ManagementMixin
from education_system.university_system.modules.domain.academics.gui.assignment_system.assignment_manager.creation import CreationMixin
from education_system.university_system.modules.domain.academics.gui.assignment_system.assignment_manager.bulk_operations import BulkOperationsMixin
from education_system.university_system.modules.domain.academics.gui.assignment_system.assignment_manager.templates import TemplatesMixin
from education_system.university_system.modules.domain.academics.gui.assignment_system.assignment_manager.statistics import StatisticsMixin
from education_system.university_system.modules.domain.academics.gui.assignment_system.assignment_manager.email_notifications import EmailNotificationsMixin
from education_system.university_system.modules.domain.academics.gui.assignment_system.assignment_manager.data_loaders import DataLoadersMixin


class AssignmentManager(
    StudentViewsMixin,
    AdminViewsMixin,
    ManagementMixin,
    CreationMixin,
    BulkOperationsMixin,
    TemplatesMixin,
    StatisticsMixin,
    EmailNotificationsMixin,
    DataLoadersMixin,
    AssignmentManagerBase,
):
    """Assignment CRUD operations and management"""
    pass
