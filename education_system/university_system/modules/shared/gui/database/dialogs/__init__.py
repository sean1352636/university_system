"""Dialog components for data backup GUI."""
from education_system.university_system.modules.shared.gui.database.dialogs.integrity_check import (
    IntegrityCheckDialog, AdvancedSettingsDialog,
)
from education_system.university_system.modules.shared.gui.database.dialogs.backup_options import (
    BackupOptionsDialog, BackupViewerDialog,
)
from education_system.university_system.modules.shared.gui.database.dialogs.restore import (
    RestoreDialog, TableSelectionDialog,
)
from education_system.university_system.modules.shared.gui.database.dialogs.validation import ValidationDialog
from education_system.university_system.modules.shared.gui.database.dialogs.report import ReportDialog
from education_system.university_system.modules.shared.gui.database.dialogs.notifications import (
    EmailConfigDialog, WebhookConfigDialog,
)
from education_system.university_system.modules.shared.gui.database.dialogs.cloud import (
    UploadDialog, DownloadDialog,
)
from education_system.university_system.modules.shared.gui.database.dialogs.export import ExportDialog
from education_system.university_system.modules.shared.gui.database.dialogs.templates import (
    TemplateSelectionDialog, TemplateManagerDialog,
)
from education_system.university_system.modules.shared.gui.database.dialogs.schedule import (
    ScheduleConfigDialog, ScheduleHistoryDialog,
)
from education_system.university_system.modules.shared.gui.database.dialogs.storage import StorageUsageDialog
from education_system.university_system.modules.shared.gui.database.dialogs.comparison import ComparisonDialog

__all__ = [
    'IntegrityCheckDialog', 'AdvancedSettingsDialog',
    'BackupOptionsDialog', 'BackupViewerDialog',
    'RestoreDialog', 'TableSelectionDialog',
    'ValidationDialog', 'ReportDialog',
    'EmailConfigDialog', 'WebhookConfigDialog',
    'UploadDialog', 'DownloadDialog',
    'ExportDialog',
    'TemplateSelectionDialog', 'TemplateManagerDialog',
    'ScheduleConfigDialog', 'ScheduleHistoryDialog',
    'StorageUsageDialog', 'ComparisonDialog',
]
