"""
Shared Services Package.

Provides common services used across the university system:
- Data Export: Export student/user data in various formats
- Batch Operations: Bulk administrative operations
"""

from education_system.university_system.modules.shared.utils.i18n import get_text, _

# Data Export
from education_system.university_system.modules.shared.services.data_exporter import (
    DataExportService,
    ExportFormat,
    ExportResult,
    StudentData,
    DataExporter,
    JSONExporter,
    CSVExporter,
    PDFExporter,
)

# Batch Operations
from education_system.university_system.modules.shared.services.batch_operations import (
    BatchOperations,
    BatchResult,
    BatchStatus,
    OperationResult,
    EnrollmentRequest,
    GradeUpdateRequest,
    BatchSizeExceeded,
)

__all__ = [
    # Data Export
    'DataExportService',
    'ExportFormat',
    'ExportResult',
    'StudentData',
    'DataExporter',
    'JSONExporter',
    'CSVExporter',
    'PDFExporter',
    # Batch Operations
    'BatchOperations',
    'BatchResult',
    'BatchStatus',
    'OperationResult',
    'EnrollmentRequest',
    'GradeUpdateRequest',
    'BatchSizeExceeded',
]
