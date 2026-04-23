"""
Data Export Functionality for the University System.

Allows users to export their data in various formats (JSON, CSV, PDF)
for portability and compliance with data access requests.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
from education_system.university_system.infrastructure.database.db import sqlite3
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from education_system.university_system.infrastructure.database.db import get_connection, DEFAULT_DB_PATH
from education_system.university_system.modules.shared.utils.activity_logger import log_export
from education_system.university_system.modules.shared.utils.i18n import get_text, _

logger = logging.getLogger(__name__)

class ExportFormat(Enum):
    """Supported export formats."""
    JSON = 'json'
    CSV = 'csv'
    PDF = 'pdf'
    ZIP = 'zip'  # All formats bundled

@dataclass
class ExportResult:
    """Result of an export operation."""
    success: bool
    format: ExportFormat
    file_path: Optional[str] = None
    file_size: int = 0
    record_count: int = 0
    error: Optional[str] = None
    content: Optional[bytes] = None  # For in-memory exports

@dataclass
class StudentData:
    """Container for student export data."""
    profile: Dict[str, Any] = field(default_factory=dict)
    academic_records: List[Dict[str, Any]] = field(default_factory=list)
    enrollments: List[Dict[str, Any]] = field(default_factory=list)
    grades: List[Dict[str, Any]] = field(default_factory=list)
    financial_records: List[Dict[str, Any]] = field(default_factory=list)
    health_records: List[Dict[str, Any]] = field(default_factory=list)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    activity_log: List[Dict[str, Any]] = field(default_factory=list)
    attendance: List[Dict[str, Any]] = field(default_factory=list)
    attendance_summary: Dict[str, Any] = field(default_factory=dict)
    export_metadata: Dict[str, Any] = field(default_factory=dict)

class DataExporter(ABC):
    """Abstract base class for data exporters."""

    @abstractmethod
    def export(self, data: Any) -> bytes:
        """Export data to bytes."""
        pass

class JSONExporter(DataExporter):
    """Export data as JSON."""

    def __init__(self, pretty: bool = True):
        self.pretty = pretty

    def export(self, data: Any) -> bytes:
        if hasattr(data, '__dict__'):
            data = self._to_dict(data)

        indent = 2 if self.pretty else None
        return json.dumps(data, indent=indent, default=str, ensure_ascii=False).encode('utf-8')

    def _to_dict(self, obj: Any) -> Any:
        if hasattr(obj, '__dict__'):
            return {k: self._to_dict(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, list):
            return [self._to_dict(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self._to_dict(v) for k, v in obj.items()}
        return obj

class CSVExporter(DataExporter):
    """Export data as CSV."""

    def export(self, data: Any) -> bytes:
        if isinstance(data, dict):
            # Export each section as separate CSV
            sections = []
            for key, value in data.items():
                if isinstance(value, list) and value:
                    sections.append(f"=== {key.upper()} ===")
                    sections.append(self._list_to_csv(value))
            return '\n\n'.join(sections).encode('utf-8')
        elif isinstance(data, list):
            return self._list_to_csv(data).encode('utf-8')
        else:
            return str(data).encode('utf-8')

    def _list_to_csv(self, data: List[Dict]) -> str:
        if not data:
            return ""

        output = io.StringIO()
        # Get all keys from all records
        all_keys = set()
        for record in data:
            if isinstance(record, dict):
                all_keys.update(record.keys())

        keys = sorted(all_keys)
        writer = csv.DictWriter(output, fieldnames=keys, extrasaction='ignore')
        writer.writeheader()

        for record in data:
            if isinstance(record, dict):
                writer.writerow(record)

        return output.getvalue()

class PDFExporter(DataExporter):
    """Export data as PDF (uses reportlab if available, falls back to text)."""

    def export(self, data: Any) -> bytes:
        try:
            return self._export_with_reportlab(data)
        except ImportError:
            logger.warning("reportlab not available, using text-based PDF fallback")
            return self._export_fallback(data)

    def _export_with_reportlab(self, data: Any) -> bytes:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Title
        elements.append(Paragraph("Data Export Report", styles['Title']))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        elements.append(Spacer(1, 20))

        # Add data sections
        if isinstance(data, dict):
            for section_name, section_data in data.items():
                elements.append(Paragraph(section_name.replace('_', ' ').title(), styles['Heading2']))

                if isinstance(section_data, list) and section_data:
                    # Create table for list data
                    if isinstance(section_data[0], dict):
                        headers = list(section_data[0].keys())[:5]  # Limit columns
                        table_data = [headers]
                        for record in section_data[:20]:  # Limit rows
                            row = [str(record.get(h, ''))[:30] for h in headers]
                            table_data.append(row)

                        table = Table(table_data)
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 8),
                            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                            ('FONTSIZE', (0, 1), (-1, -1), 7),
                            ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ]))
                        elements.append(table)
                        if len(section_data) > 20:
                            elements.append(Paragraph(f"... and {len(section_data) - 20} more records", styles['Normal']))
                elif isinstance(section_data, dict):
                    for k, v in section_data.items():
                        elements.append(Paragraph(f"<b>{k}:</b> {str(v)[:100]}", styles['Normal']))

                elements.append(Spacer(1, 15))

        doc.build(elements)
        return buffer.getvalue()

    def _export_fallback(self, data: Any) -> bytes:
        """Simple text-based fallback when reportlab is not available."""
        lines = [
            "=" * 60,
            "DATA EXPORT REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            ""
        ]

        if isinstance(data, dict):
            for section_name, section_data in data.items():
                lines.append(f"\n--- {section_name.upper()} ---")
                if isinstance(section_data, list):
                    for item in section_data[:10]:
                        lines.append(json.dumps(item, default=str)[:200])
                    if len(section_data) > 10:
                        lines.append(f"... and {len(section_data) - 10} more records")
                elif isinstance(section_data, dict):
                    for k, v in section_data.items():
                        lines.append(f"  {k}: {str(v)[:100]}")

        return '\n'.join(lines).encode('utf-8')

class DataExportService:
    """
    Service for exporting student and user data.

    Example:
        >>> exporter = DataExportService()
        >>>
        >>> # Export student data
        >>> result = exporter.export_student_data(
        ...     student_id='12345',
        ...     format=ExportFormat.JSON
        ... )
        >>> if result.success:
        ...     print(f"Exported {result.record_count} records")
    """

    def __init__(self, db_path: Optional[str] = None, export_dir: Optional[str] = None):
        """
        Initialize export service.

        Args:
            db_path: Database path
            export_dir: Directory for file exports
        """
        self.db_path = db_path or DEFAULT_DB_PATH

        if export_dir:
            self.export_dir = Path(export_dir)
        else:
            from education_system.university_system.modules.shared.constants import paths
            self.export_dir = Path(paths.DB_EXPORTS_DIR)

        self.export_dir.mkdir(parents=True, exist_ok=True)

        self.exporters = {
            ExportFormat.JSON: JSONExporter(),
            ExportFormat.CSV: CSVExporter(),
            ExportFormat.PDF: PDFExporter(),
        }

        logger.info(f"DataExportService initialized, export_dir: {self.export_dir}")

    def collect_student_data(self, student_id: str) -> StudentData:
        """
        Collect all data for a student.

        Args:
            student_id: The student ID

        Returns:
            StudentData object with all collected data
        """
        data = StudentData()
        data.export_metadata = {
            'student_id': student_id,
            'export_date': datetime.now().isoformat(),
            'version': '1.0',
        }

        with get_connection(self.db_path) as conn:
            # Get student profile
            cursor = conn.execute('''
                SELECT * FROM students WHERE student_id = ?
            ''', (student_id,))
            row = cursor.fetchone()
            if row:
                data.profile = dict(row) if hasattr(row, 'keys') else {'id': row[0]}

            # Get user account info (sanitized)
            if data.profile.get('user_id'):
                user_id = data.profile['user_id']
                cursor = conn.execute('''
                    SELECT id, username, email, first_name, last_name, role, created_at
                    FROM users WHERE id = ?
                ''', (user_id,))
                row = cursor.fetchone()
                if row:
                    data.profile['user'] = dict(row) if hasattr(row, 'keys') else {}

            # Get enrollments (enrollments table in some deployments, student_modules in others)
            try:
                cursor = conn.execute('''
                    SELECT e.*, c.name as course_name, c.code as course_code
                    FROM enrollments e
                    LEFT JOIN courses c ON e.course_id = c.id
                    WHERE e.student_id = ?
                ''', (student_id,))
                data.enrollments = [dict(row) if hasattr(row, 'keys') else {} for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                try:
                    cursor = conn.execute('''
                        SELECT * FROM student_modules WHERE student_id = ?
                    ''', (student_id,))
                    data.enrollments = [dict(row) if hasattr(row, 'keys') else {} for row in cursor.fetchall()]
                except sqlite3.OperationalError:
                    pass

            # Get grades
            try:
                cursor = conn.execute('''
                    SELECT * FROM grades WHERE student_id = ?
                ''', (student_id,))
                data.grades = [dict(row) if hasattr(row, 'keys') else {} for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                pass  # Table might not exist

            # Get financial records (if exists)
            try:
                cursor = conn.execute('''
                    SELECT * FROM financial_transactions WHERE student_id = ?
                ''', (student_id,))
                data.financial_records = [dict(row) if hasattr(row, 'keys') else {} for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                pass

            # Get attendance records (from enhanced attendance tracker)
            try:
                cursor = conn.execute('''
                    SELECT id, student_id, module_code, date, status, notes,
                           recorded_by, recorded_at, check_in_method,
                           location_data, session_id, makeup_for_date,
                           verification_status
                    FROM attendance_records
                    WHERE student_id = ?
                    ORDER BY date DESC, recorded_at DESC
                ''', (student_id,))
                data.attendance = [dict(row) if hasattr(row, 'keys') else {} for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                pass  # attendance_records table may not exist in this deployment

            # Fallback / supplement: legacy `attendance` table used by some installs
            if not data.attendance:
                try:
                    cursor = conn.execute('''
                        SELECT * FROM attendance WHERE student_id = ? ORDER BY date DESC
                    ''', (student_id,))
                    data.attendance = [dict(row) if hasattr(row, 'keys') else {} for row in cursor.fetchall()]
                except sqlite3.OperationalError:
                    pass

            # Build a small summary (counts by status + attendance rate)
            if data.attendance:
                status_counts: Dict[str, int] = {}
                for record in data.attendance:
                    status = str(record.get('status') or 'unknown').lower()
                    status_counts[status] = status_counts.get(status, 0) + 1
                total = sum(status_counts.values())
                present = status_counts.get('present', 0) + status_counts.get('late', 0)
                data.attendance_summary = {
                    'total_records': total,
                    'status_counts': status_counts,
                    'attendance_rate_percent': round((present / total) * 100, 2) if total else 0.0,
                }

            # Get messages
            if data.profile.get('user_id'):
                cursor = conn.execute('''
                    SELECT m.id, m.subject, m.message, m.sent_at, m.is_read,
                           u.username as sender_name
                    FROM messages m
                    LEFT JOIN users u ON m.sender_id = u.id
                    WHERE m.recipient_id = ?
                    ORDER BY m.sent_at DESC
                    LIMIT 1000
                ''', (data.profile['user_id'],))
                data.messages = [dict(row) if hasattr(row, 'keys') else {} for row in cursor.fetchall()]

        return data

    def export_student_data(
        self,
        student_id: str,
        format: Union[ExportFormat, str] = ExportFormat.JSON,
        save_to_file: bool = True,
    ) -> ExportResult:
        """
        Export student data to specified format.

        Args:
            student_id: Student ID to export
            format: Export format (json, csv, pdf, zip)
            save_to_file: Whether to save to file or return bytes

        Returns:
            ExportResult with file path or content
        """
        if isinstance(format, str):
            format = ExportFormat(format.lower())

        logger.info(f"Exporting data for student {student_id} as {format.value}")

        try:
            # Collect data
            data = self.collect_student_data(student_id)
            data_dict = self._to_dict(data)

            record_count = sum(
                len(v) if isinstance(v, list) else 1
                for v in data_dict.values()
                if v
            )

            # Export based on format
            if format == ExportFormat.ZIP:
                content = self._create_zip_export(data_dict)
            else:
                exporter = self.exporters.get(format)
                if not exporter:
                    return ExportResult(success=False, format=format, error=f"Unsupported format: {format}")
                content = exporter.export(data_dict)

            # Save to file or return content
            if save_to_file:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"student_{student_id}_export_{timestamp}.{format.value}"
                file_path = self.export_dir / filename

                with open(file_path, 'wb') as f:
                    f.write(content)

                # Log export activity
                log_export('student_data', format.value)

                return ExportResult(
                    success=True,
                    format=format,
                    file_path=str(file_path),
                    file_size=len(content),
                    record_count=record_count,
                )
            else:
                return ExportResult(
                    success=True,
                    format=format,
                    content=content,
                    file_size=len(content),
                    record_count=record_count,
                )

        except Exception as e:
            logger.error(f"Export failed for student {student_id}: {e}")
            return ExportResult(
                success=False,
                format=format,
                error=str(e),
            )

    def _create_zip_export(self, data: Dict[str, Any]) -> bytes:
        """Create a ZIP file with all formats."""
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add JSON
            json_content = self.exporters[ExportFormat.JSON].export(data)
            zf.writestr('data.json', json_content)

            # Add CSV
            csv_content = self.exporters[ExportFormat.CSV].export(data)
            zf.writestr('data.csv', csv_content)

            # Add PDF
            pdf_content = self.exporters[ExportFormat.PDF].export(data)
            zf.writestr('data.pdf', pdf_content)

            # Add metadata
            metadata = {
                'export_date': datetime.now().isoformat(),
                'formats': ['json', 'csv', 'pdf'],
                'version': '1.0',
            }
            zf.writestr('metadata.json', json.dumps(metadata, indent=2))

        return buffer.getvalue()

    def _to_dict(self, obj: Any) -> Any:
        """Convert dataclass or object to dict."""
        if hasattr(obj, '__dict__'):
            result = {}
            for k, v in obj.__dict__.items():
                result[k] = self._to_dict(v)
            return result
        elif isinstance(obj, list):
            return [self._to_dict(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self._to_dict(v) for k, v in obj.items()}
        return obj

    def list_exports(self, student_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List existing export files.

        Args:
            student_id: Filter by student ID

        Returns:
            List of export file info
        """
        exports = []

        for file_path in self.export_dir.glob('*'):
            if file_path.is_file():
                if student_id and student_id not in file_path.name:
                    continue

                exports.append({
                    'filename': file_path.name,
                    'path': str(file_path),
                    'size': file_path.stat().st_size,
                    'created': datetime.fromtimestamp(file_path.stat().st_ctime).isoformat(),
                })

        return sorted(exports, key=lambda x: x['created'], reverse=True)

    def cleanup_old_exports(self, days: int = 30) -> int:
        """
        Remove export files older than specified days.

        Args:
            days: Remove files older than this

        Returns:
            Number of files removed
        """
        cutoff = datetime.now().timestamp() - (days * 86400)
        removed = 0

        for file_path in self.export_dir.glob('*'):
            if file_path.is_file() and file_path.stat().st_ctime < cutoff:
                file_path.unlink()
                removed += 1

        if removed > 0:
            logger.info(f"Cleaned up {removed} old export files")

        return removed

__all__ = [
    'DataExportService',
    'ExportFormat',
    'ExportResult',
    'StudentData',
    'DataExporter',
    'JSONExporter',
    'CSVExporter',
    'PDFExporter',
]
