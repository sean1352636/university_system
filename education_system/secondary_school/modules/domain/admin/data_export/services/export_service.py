"""Data export service — CSV exports."""

import csv
import io
import logging
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class ExportService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def export_students(self, status=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM students WHERE 1=1"
            params = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY last_name, first_name"
            rows = conn.execute(sql, params).fetchall()
            return self._rows_to_csv(rows)
        finally:
            conn.close()

    def export_grades(self, subject_id=None, term=None):
        conn = self._conn()
        try:
            sql = """SELECT g.*, s.first_name, s.last_name, s.student_id as stu_code,
                     sub.title as subject_title, sub.subject_code
                     FROM grades g
                     JOIN students s ON g.student_id = s.id
                     JOIN subjects sub ON g.subject_id = sub.id
                     WHERE 1=1"""
            params = []
            if subject_id:
                sql += " AND g.subject_id = ?"
                params.append(subject_id)
            if term:
                sql += " AND g.term = ?"
                params.append(term)
            sql += " ORDER BY s.last_name, s.first_name"
            rows = conn.execute(sql, params).fetchall()
            return self._rows_to_csv(rows)
        finally:
            conn.close()

    def export_attendance(self, date_from=None, date_to=None):
        conn = self._conn()
        try:
            sql = """SELECT ar.*, s.first_name, s.last_name, s.student_id as stu_code
                     FROM attendance_records ar
                     JOIN students s ON ar.student_id = s.id
                     WHERE 1=1"""
            params = []
            if date_from:
                sql += " AND ar.date >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND ar.date <= ?"
                params.append(date_to)
            sql += " ORDER BY ar.date, s.last_name"
            rows = conn.execute(sql, params).fetchall()
            return self._rows_to_csv(rows)
        finally:
            conn.close()

    def export_behaviour(self, student_id=None):
        conn = self._conn()
        try:
            sql = """SELECT br.*, s.first_name, s.last_name, s.student_id as stu_code
                     FROM behaviour_records br
                     JOIN students s ON br.student_id = s.id
                     WHERE 1=1"""
            params = []
            if student_id:
                sql += " AND br.student_id = ?"
                params.append(student_id)
            sql += " ORDER BY br.incident_date DESC"
            rows = conn.execute(sql, params).fetchall()
            return self._rows_to_csv(rows)
        finally:
            conn.close()

    def export_timetable(self):
        conn = self._conn()
        try:
            sql = """SELECT ts.*, sub.title as subject_title, sub.subject_code
                     FROM timetable_slots ts
                     JOIN subjects sub ON ts.subject_id = sub.id
                     ORDER BY ts.day_of_week, ts.period"""
            rows = conn.execute(sql).fetchall()
            return self._rows_to_csv(rows)
        finally:
            conn.close()

    @staticmethod
    def _rows_to_csv(rows):
        if not rows:
            return ""
        output = io.StringIO()
        keys = rows[0].keys()
        writer = csv.DictWriter(output, fieldnames=keys)
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(r))
        return output.getvalue()
