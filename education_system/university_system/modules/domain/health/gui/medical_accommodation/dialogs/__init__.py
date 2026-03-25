# dialogs/__init__.py
# Re-exports all dialog classes for convenient imports.

from education_system.university_system.modules.domain.health.gui.medical_accommodation.dialogs.accommodation_dialog import AccommodationDialog
from education_system.university_system.modules.domain.health.gui.medical_accommodation.dialogs.details_dialog import DetailsDialog
from education_system.university_system.modules.domain.health.gui.medical_accommodation.dialogs.document_upload import DocumentUploadDialog
from education_system.university_system.modules.domain.health.gui.medical_accommodation.dialogs.export_filter import ExportFilterDialog
from education_system.university_system.modules.domain.health.gui.medical_accommodation.dialogs.import_result import ImportResultDialog
from education_system.university_system.modules.domain.health.gui.medical_accommodation.dialogs.database_info import DatabaseInfoDialog
from education_system.university_system.modules.domain.health.gui.medical_accommodation.dialogs.settings import SettingsDialog
from education_system.university_system.modules.domain.health.gui.medical_accommodation.dialogs.help import HelpDialog

__all__ = [
    'AccommodationDialog',
    'DetailsDialog',
    'DocumentUploadDialog',
    'ExportFilterDialog',
    'ImportResultDialog',
    'DatabaseInfoDialog',
    'SettingsDialog',
    'HelpDialog',
]
