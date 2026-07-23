"""
Batch Operations Mixins Package

Contains mixin classes that compose the EnhancedBatchOperationManager.
Each mixin provides a cohesive group of related methods.
"""

from education_system.post_18.university_system.modules.shared.gui.batch_operations.mixins.import_handlers import ImportHandlersMixin
from education_system.post_18.university_system.modules.shared.gui.batch_operations.mixins.batch_updates import BatchUpdatesMixin
from education_system.post_18.university_system.modules.shared.gui.batch_operations.mixins.validation import ValidationMixin
from education_system.post_18.university_system.modules.shared.gui.batch_operations.mixins.duplicates import DuplicatesMixin
from education_system.post_18.university_system.modules.shared.gui.batch_operations.mixins.module_operations import ModuleOperationsMixin
from education_system.post_18.university_system.modules.shared.gui.batch_operations.mixins.grade_management import GradeManagementMixin
from education_system.post_18.university_system.modules.shared.gui.batch_operations.mixins.export_reporting import ExportReportingMixin
from education_system.post_18.university_system.modules.shared.gui.batch_operations.mixins.data_quality import DataQualityMixin
from education_system.post_18.university_system.modules.shared.gui.batch_operations.mixins.backup_restore import BackupRestoreMixin
from education_system.post_18.university_system.modules.shared.gui.batch_operations.mixins.templates import TemplatesMixin
from education_system.post_18.university_system.modules.shared.gui.batch_operations.mixins.scheduling import SchedulingMixin
from education_system.post_18.university_system.modules.shared.gui.batch_operations.mixins.external_integration import ExternalIntegrationMixin
from education_system.post_18.university_system.modules.shared.gui.batch_operations.mixins.api_service import ApiServiceMixin
from education_system.post_18.university_system.modules.shared.gui.batch_operations.mixins.utils import UtilsMixin

__all__ = [
    'ImportHandlersMixin',
    'BatchUpdatesMixin',
    'ValidationMixin',
    'DuplicatesMixin',
    'ModuleOperationsMixin',
    'GradeManagementMixin',
    'ExportReportingMixin',
    'DataQualityMixin',
    'BackupRestoreMixin',
    'TemplatesMixin',
    'SchedulingMixin',
    'ExternalIntegrationMixin',
    'ApiServiceMixin',
    'UtilsMixin',
]
