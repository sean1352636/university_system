"""HESA data export service for statutory XML returns."""

import defusedxml.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction


class HESAExportService:
    """Service for managing HESA statutory data returns."""

    def __init__(self):
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        with transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hesa_returns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    academic_year TEXT NOT NULL,
                    return_type TEXT NOT NULL,
                    status TEXT DEFAULT 'draft',
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    submitted_at TEXT,
                    xml_data TEXT,
                    notes TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hesa_field_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    return_type TEXT NOT NULL,
                    hesa_field TEXT NOT NULL,
                    local_field TEXT NOT NULL,
                    transform_rule TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hesa_submission_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    return_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    performed_by TEXT,
                    performed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (return_id) REFERENCES hesa_returns(id)
                )
            """)
            conn.commit()

    def create_return(self, academic_year: str, return_type: str, created_by: str = None, notes: str = None) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO hesa_returns (academic_year, return_type, created_by, notes) VALUES (?, ?, ?, ?)",
                (academic_year, return_type, created_by, notes)
            )
            conn.commit()
            return cursor.lastrowid

    def get_return(self, return_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM hesa_returns WHERE id = ?", (return_id,)).fetchone()
            return dict(row) if row else None

    def list_returns(self, status: str = None) -> List[Dict]:
        with get_connection() as conn:
            if status:
                rows = conn.execute("SELECT * FROM hesa_returns WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM hesa_returns ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def update_return_status(self, return_id: int, status: str, performed_by: str = None) -> bool:
        with transaction() as conn:
            conn.execute("UPDATE hesa_returns SET status = ? WHERE id = ?", (status, return_id))
            if status == 'submitted':
                conn.execute("UPDATE hesa_returns SET submitted_at = ? WHERE id = ?", (datetime.now().isoformat(), return_id))
            conn.execute(
                "INSERT INTO hesa_submission_log (return_id, action, details, performed_by) VALUES (?, ?, ?, ?)",
                (return_id, f"Status changed to {status}", None, performed_by)
            )
            conn.commit()
            return True

    def generate_xml_export(self, return_id: int) -> str:
        """Generate HESA XML from student/staff data."""
        ret = self.get_return(return_id)
        if not ret:
            return ""

        root = ET.Element("HESAReturn")
        root.set("AcademicYear", ret['academic_year'])
        root.set("ReturnType", ret['return_type'])
        root.set("GeneratedAt", datetime.now().isoformat())

        institution = ET.SubElement(root, "Institution")
        ET.SubElement(institution, "UKPRN").text = "10000001"
        ET.SubElement(institution, "InstitutionName").text = "University"

        if ret['return_type'] == 'Student':
            students_elem = ET.SubElement(root, "StudentRecords")
            with get_connection() as conn:
                try:
                    rows = conn.execute("SELECT * FROM students LIMIT 1000").fetchall()
                    for row in rows:
                        s = dict(row)
                        student_elem = ET.SubElement(students_elem, "Student")
                        ET.SubElement(student_elem, "StudentID").text = str(s.get('student_id', ''))
                        ET.SubElement(student_elem, "FirstName").text = str(s.get('first_name', s.get('name', '')))
                        ET.SubElement(student_elem, "LastName").text = str(s.get('last_name', ''))
                        ET.SubElement(student_elem, "Course").text = str(s.get('course', s.get('program', '')))
                        ET.SubElement(student_elem, "YearOfStudy").text = str(s.get('year_of_study', ''))
                except Exception:
                    ET.SubElement(students_elem, "Error").text = "Could not retrieve student data"

        xml_str = ET.tostring(root, encoding='unicode', xml_declaration=True)

        with transaction() as conn:
            conn.execute("UPDATE hesa_returns SET xml_data = ? WHERE id = ?", (xml_str, return_id))
            conn.commit()

        return xml_str

    def add_field_mapping(self, return_type: str, hesa_field: str, local_field: str, transform_rule: str = None) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO hesa_field_mappings (return_type, hesa_field, local_field, transform_rule) VALUES (?, ?, ?, ?)",
                (return_type, hesa_field, local_field, transform_rule)
            )
            conn.commit()
            return cursor.lastrowid

    def get_field_mappings(self, return_type: str = None) -> List[Dict]:
        with get_connection() as conn:
            if return_type:
                rows = conn.execute("SELECT * FROM hesa_field_mappings WHERE return_type = ?", (return_type,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM hesa_field_mappings").fetchall()
            return [dict(r) for r in rows]

    def log_submission_action(self, return_id: int, action: str, details: str = None, performed_by: str = None) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO hesa_submission_log (return_id, action, details, performed_by) VALUES (?, ?, ?, ?)",
                (return_id, action, details, performed_by)
            )
            conn.commit()
            return cursor.lastrowid

    def get_submission_log(self, return_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM hesa_submission_log WHERE return_id = ? ORDER BY performed_at DESC", (return_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_return_statistics(self) -> Dict:
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM hesa_returns").fetchone()[0]
            by_status = {}
            for row in conn.execute("SELECT status, COUNT(*) as cnt FROM hesa_returns GROUP BY status").fetchall():
                by_status[row[0]] = row[1]
            return {"total": total, "by_status": by_status}
