"""
Data Management Infrastructure

Provides backup automation, data export and table export.
"""

from education_system.systems.university.infrastructure.data_management.backup_scheduler import (
    BackupScheduler,
    get_backup_scheduler,
    schedule_backups,
)

# Optional imports
try:
    from education_system.systems.university.services.data_exporter import (
        DataExporter,
        DataExportService,
        ExportFormat,
    )
    DATA_EXPORTER_AVAILABLE = True
except ImportError:
    DATA_EXPORTER_AVAILABLE = False
    DataExporter = None
    DataExportService = None
    ExportFormat = None

__all__ = [
    # Backup Scheduling
    'BackupScheduler',
    'get_backup_scheduler',
    'schedule_backups',
    # Data Export (optional)
    'DataExporter',
    'DataExportService',
    'ExportFormat',
    'DATA_EXPORTER_AVAILABLE',
]
