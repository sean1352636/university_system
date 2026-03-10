"""Data export service for the Primary School Management System."""

import csv
import logging
from education_system.primary_school.infrastructure.database.db import connect
import traceback

logger = logging.getLogger(__name__)


class DataExportService:
    """Export data to CSV files."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def export_pupils_csv(self, file_path, year_group=None, status="Active"):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM pupils WHERE 1=1"
            params = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if year_group:
                sql += " AND year_group = ?"
                params.append(year_group)
            sql += " ORDER BY year_group, last_name, first_name"
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            if not rows:
                logger.info("No pupils found for export")
                return 0
            keys = rows[0].keys()
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                for row in rows:
                    writer.writerow(dict(row))
            logger.info("Exported %d pupils to %s", len(rows), file_path)
            return len(rows)
        finally:
            conn.close()

    def export_attendance_csv(self, file_path, date_from=None, date_to=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM attendance_records WHERE 1=1"
            params = []
            if date_from:
                sql += " AND date >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND date <= ?"
                params.append(date_to)
            sql += " ORDER BY date, pupil_id"
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            if not rows:
                logger.info("No attendance records found for export")
                return 0
            keys = rows[0].keys()
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                for row in rows:
                    writer.writerow(dict(row))
            logger.info("Exported %d attendance records to %s", len(rows), file_path)
            return len(rows)
        finally:
            conn.close()

    def export_assessments_csv(self, file_path, academic_year=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM assessments WHERE 1=1"
            params = []
            if academic_year:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY pupil_id, subject, assessment_date"
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            if not rows:
                logger.info("No assessments found for export")
                return 0
            keys = rows[0].keys()
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                for row in rows:
                    writer.writerow(dict(row))
            logger.info("Exported %d assessments to %s", len(rows), file_path)
            return len(rows)
        finally:
            conn.close()
