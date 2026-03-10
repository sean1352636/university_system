"""
DEPRECATED: Database GUI components have been moved to modules/shared/gui/database/

This module provides backward compatibility for existing imports.
New code should import from education_system.university_system.modules.shared.gui.database instead.
"""

import warnings

warnings.warn(
    "Importing from education_system.university_system.infrastructure.database.gui is deprecated. "
    "Please import from education_system.university_system.modules.shared.gui.database instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location for backward compatibility
from education_system.university_system.modules.shared.gui.database.backup_gui import BackupGUI
from education_system.university_system.modules.shared.gui.database.metadata import (
    BackupMetadata,
    ProgressTracker,
)
from education_system.university_system.modules.shared.gui.database.dialogs import (
    IntegrityCheckDialog,
    AdvancedSettingsDialog,
    ScheduleHistoryDialog,
    BackupOptionsDialog,
    BackupViewerDialog,
    RestoreDialog,
    TableSelectionDialog,
    ValidationDialog,
    ReportDialog,
    EmailConfigDialog,
    WebhookConfigDialog,
    UploadDialog,
    DownloadDialog,
    ExportDialog,
    TemplateSelectionDialog,
    TemplateManagerDialog,
    ScheduleConfigDialog,
    StorageUsageDialog,
    ComparisonDialog,
)
from education_system.university_system.modules.shared.gui.database.entry_points import (
    start_backup_gui,
    display_enhanced_backup_menu_gui,
    display_backup_menu_gui,
    open_data_backup_gui,
    create_backup_gui,
    backup_before_operation_gui,
)
from education_system.university_system.modules.shared.gui.database.config import (
    save_gui_config,
    load_gui_config,
    save_config,
    load_config,
)
from education_system.university_system.modules.shared.gui.database.scheduling import (
    start_scheduler,
    stop_scheduler,
    scheduled_backup_job,
    get_connection,
    parse_cron_schedule,
)
from education_system.university_system.modules.shared.gui.database.operations import (
    get_database_tables_from_connection,
    create_incremental_backup,
    generate_advanced_statistics,
    restore_from_backup,
    restore_partial_tables,
    generate_backup_statistics,
    get_log_file,
    list_backup_templates,
    save_backup_template,
    load_backup_template,
    export_to_csv,
    export_to_json,
    export_to_xml,
    export_to_pdf,
    export_to_txt,
    create_schema_only_backup,
    compare_backups,
)

__all__ = [
    'BackupGUI',
    'BackupMetadata',
    'ProgressTracker',
    'IntegrityCheckDialog',
    'AdvancedSettingsDialog',
    'ScheduleHistoryDialog',
    'BackupOptionsDialog',
    'BackupViewerDialog',
    'RestoreDialog',
    'TableSelectionDialog',
    'ValidationDialog',
    'ReportDialog',
    'EmailConfigDialog',
    'WebhookConfigDialog',
    'UploadDialog',
    'DownloadDialog',
    'ExportDialog',
    'TemplateSelectionDialog',
    'TemplateManagerDialog',
    'ScheduleConfigDialog',
    'StorageUsageDialog',
    'ComparisonDialog',
    'start_backup_gui',
    'display_enhanced_backup_menu_gui',
    'display_backup_menu_gui',
    'open_data_backup_gui',
    'create_backup_gui',
    'backup_before_operation_gui',
    'save_gui_config',
    'load_gui_config',
    'start_scheduler',
    'stop_scheduler',
    'scheduled_backup_job',
    'get_connection',
    'parse_cron_schedule',
    'save_config',
    'load_config',
    'get_database_tables_from_connection',
    'create_incremental_backup',
    'generate_advanced_statistics',
    'restore_from_backup',
    'restore_partial_tables',
    'generate_backup_statistics',
    'get_log_file',
    'list_backup_templates',
    'save_backup_template',
    'load_backup_template',
    'export_to_csv',
    'export_to_json',
    'export_to_xml',
    'export_to_pdf',
    'export_to_txt',
    'create_schema_only_backup',
    'compare_backups',
]
