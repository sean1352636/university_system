"""
Database GUI components.

This module contains GUI components for database backup/management that were moved from
infrastructure/database/gui/ to maintain proper architectural layering.

Submodules:
- backup_gui.py: Main BackupGUI class
- config.py: Configuration management
- metadata.py: ProgressTracker, BackupMetadata
- shared_imports.py: Common imports and setup
- entry_points.py: Entry point functions and CLI
- dialogs/: Dialog classes (12 files)
- operations/: Backup operations (5 files)
- scheduling/: Cron and scheduler (2 files)
"""

# Classes
from education_system.systems.university.interfaces.gui.shell.database.backup_gui import BackupGUI
from education_system.systems.university.interfaces.gui.shell.database.metadata import (
    BackupMetadata,
    ProgressTracker,
)

# Dialogs
from education_system.systems.university.interfaces.gui.shell.database.dialogs import (
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

# Entry points
from education_system.systems.university.interfaces.gui.shell.database.entry_points import (
    start_backup_gui,
    display_enhanced_backup_menu_gui,
    display_backup_menu_gui,
    open_data_backup_gui,
    create_backup_gui,
    backup_before_operation_gui,
)

# Config
from education_system.systems.university.interfaces.gui.shell.database.config import (
    save_gui_config,
    load_gui_config,
    save_config,
    load_config,
)

# Scheduling
from education_system.systems.university.interfaces.gui.shell.database.scheduling import (
    start_scheduler,
    stop_scheduler,
    scheduled_backup_job,
    get_connection,
    parse_cron_schedule,
)

# Operations
from education_system.systems.university.interfaces.gui.shell.database.operations import (
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
