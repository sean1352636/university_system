"""
Data Management Infrastructure

Provides backup automation, data validation, export/import, and archiving.
"""

from education_system.systems.university.infrastructure.data_management.backup_scheduler import (
    BackupScheduler,
    get_backup_scheduler,
    schedule_backups,
)

# Optional imports (will be added in future versions)
try:
    from education_system.systems.university.infrastructure.data_management.data_validator import (
        DataValidator,
        ValidationResult,
        validate_database,
    )
    DATA_VALIDATOR_AVAILABLE = True
except ImportError:
    DATA_VALIDATOR_AVAILABLE = False
    DataValidator = None
    ValidationResult = None
    validate_database = None

try:
    from education_system.systems.university.services.data_exporter import (
        DataExporter,
        ExportFormat,
        export_data,
    )
    DATA_EXPORTER_AVAILABLE = True
except ImportError:
    DATA_EXPORTER_AVAILABLE = False
    DataExporter = None
    ExportFormat = None
    export_data = None

__all__ = [
    # Backup Scheduling
    'BackupScheduler',
    'get_backup_scheduler',
    'schedule_backups',
    # Data Validation (optional)
    'DataValidator',
    'ValidationResult',
    'validate_database',
    'DATA_VALIDATOR_AVAILABLE',
    # Data Export (optional)
    'DataExporter',
    'ExportFormat',
    'export_data',
    'DATA_EXPORTER_AVAILABLE',
]
