"""
Shared Services Package.

Provides common services used across the university system:
- Data Export: Export student/user data in various formats
- Batch Operations: Bulk administrative operations
"""

from education_system.systems.university.infrastructure.i18n import get_text, _

# Data Export
from education_system.systems.university.services.data_exporter import (
    DataExportService,
    ExportFormat,
    ExportResult,
    StudentData,
    DataExporter,
    JSONExporter,
    CSVExporter,
    PDFExporter,
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
]
