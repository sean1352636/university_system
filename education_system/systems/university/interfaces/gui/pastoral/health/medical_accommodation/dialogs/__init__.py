# Medical-accommodation dialogs subpackage — canonical aggregator.
#
# Re-exports the 8 sibling dialog classes (Accommodation, Details,
# DocumentUpload, ExportFilter, ImportResult, DatabaseInfo, Settings, Help)
# so callers can import them in one block. This is a normal Python package
# init, not a back-compat shim.

from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation.dialogs.accommodation_dialog import AccommodationDialog
from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation.dialogs.details_dialog import DetailsDialog
from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation.dialogs.document_upload import DocumentUploadDialog
from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation.dialogs.export_filter import ExportFilterDialog
from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation.dialogs.import_result import ImportResultDialog
from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation.dialogs.database_info import DatabaseInfoDialog
from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation.dialogs.settings import SettingsDialog
from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation.dialogs.help import HelpDialog

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
