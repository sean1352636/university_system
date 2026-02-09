"""Dialog components for data backup GUI."""
from university_system.modules.shared.gui.database.dialogs.integrity_check import (
    IntegrityCheckDialog, AdvancedSettingsDialog,
)
from university_system.modules.shared.gui.database.dialogs.backup_options import (
    BackupOptionsDialog, BackupViewerDialog,
)
from university_system.modules.shared.gui.database.dialogs.restore import (
    RestoreDialog, TableSelectionDialog,
)
from university_system.modules.shared.gui.database.dialogs.validation import ValidationDialog
from university_system.modules.shared.gui.database.dialogs.report import ReportDialog
from university_system.modules.shared.gui.database.dialogs.notifications import (
    EmailConfigDialog, WebhookConfigDialog,
)
from university_system.modules.shared.gui.database.dialogs.cloud import (
    UploadDialog, DownloadDialog,
)
from university_system.modules.shared.gui.database.dialogs.export import ExportDialog
from university_system.modules.shared.gui.database.dialogs.templates import (
    TemplateSelectionDialog, TemplateManagerDialog,
)
from university_system.modules.shared.gui.database.dialogs.schedule import (
    ScheduleConfigDialog, ScheduleHistoryDialog,
)
from university_system.modules.shared.gui.database.dialogs.storage import StorageUsageDialog
from university_system.modules.shared.gui.database.dialogs.comparison import ComparisonDialog

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
