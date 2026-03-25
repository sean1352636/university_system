"""Automated clearing and adjustment workflow for admissions."""

from datetime import datetime
from typing import Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction


class ClearingAdjustmentService:
    """Service for clearing and adjustment admissions workflow."""

    def __init__(self):
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        with transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS clearing_vacancies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_code TEXT NOT NULL,
                    course_name TEXT NOT NULL,
                    department TEXT,
                    available_places INTEGER DEFAULT 0,
                    minimum_tariff INTEGER DEFAULT 0,
                    requirements TEXT,
                    is_active INTEGER DEFAULT 1,
                    academic_year TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS clearing_applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    applicant_name TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    ucas_id TEXT,
                    tariff_points INTEGER DEFAULT 0,
                    qualifications TEXT,
                    preferred_course TEXT,
                    status TEXT DEFAULT 'pending',
                    applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    processed_by TEXT,
                    processed_at TEXT,
                    notes TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS adjustment_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    original_course TEXT,
                    requested_course TEXT,
                    reason TEXT,
                    current_grades TEXT,
                    status TEXT DEFAULT 'pending',
                    requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    decided_by TEXT,
                    decided_at TEXT
                )
            """)
            conn.commit()

    def add_vacancy(self, course_code: str, course_name: str, department: str = None,
                    available_places: int = 0, minimum_tariff: int = 0,
                    requirements: str = None, academic_year: str = None) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO clearing_vacancies (course_code, course_name, department, available_places, minimum_tariff, requirements, academic_year) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (course_code, course_name, department, available_places, minimum_tariff, requirements, academic_year)
            )
            conn.commit()
            return cursor.lastrowid

    def update_vacancy(self, vacancy_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        kwargs['updated_at'] = datetime.now().isoformat()
        from education_system.shared.database.sql_safety import validate_identifier
        sets = ", ".join(f"{validate_identifier(k)} = ?" for k in kwargs)
        with transaction() as conn:
            conn.execute(f"UPDATE clearing_vacancies SET {sets} WHERE id = ?", (*kwargs.values(), vacancy_id))
            conn.commit()
            return True

    def list_vacancies(self, active_only: bool = True) -> List[Dict]:
        with get_connection() as conn:
            if active_only:
                rows = conn.execute("SELECT * FROM clearing_vacancies WHERE is_active = 1 AND available_places > 0 ORDER BY course_name").fetchall()
            else:
                rows = conn.execute("SELECT * FROM clearing_vacancies ORDER BY course_name").fetchall()
            return [dict(r) for r in rows]

    def get_available_courses(self, min_tariff: int = 0) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM clearing_vacancies WHERE is_active = 1 AND available_places > 0 AND minimum_tariff <= ? ORDER BY course_name",
                (min_tariff,)
            ).fetchall()
            return [dict(r) for r in rows]

    def submit_clearing_application(self, applicant_name: str, email: str = None, phone: str = None,
                                     ucas_id: str = None, tariff_points: int = 0,
                                     qualifications: str = None, preferred_course: str = None) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO clearing_applications (applicant_name, email, phone, ucas_id, tariff_points, qualifications, preferred_course) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (applicant_name, email, phone, ucas_id, tariff_points, qualifications, preferred_course)
            )
            conn.commit()
            return cursor.lastrowid

    def get_application(self, app_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM clearing_applications WHERE id = ?", (app_id,)).fetchone()
            return dict(row) if row else None

    def list_applications(self, status: str = None) -> List[Dict]:
        with get_connection() as conn:
            if status:
                rows = conn.execute("SELECT * FROM clearing_applications WHERE status = ? ORDER BY applied_at DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM clearing_applications ORDER BY applied_at DESC").fetchall()
            return [dict(r) for r in rows]

    def update_application_status(self, app_id: int, status: str, processed_by: str = None) -> bool:
        with transaction() as conn:
            conn.execute(
                "UPDATE clearing_applications SET status = ?, processed_by = ?, processed_at = ? WHERE id = ?",
                (status, processed_by, datetime.now().isoformat(), app_id)
            )
            if status == 'accepted':
                app = self.get_application(app_id)
                if app and app.get('preferred_course'):
                    conn.execute(
                        "UPDATE clearing_vacancies SET available_places = MAX(available_places - 1, 0) WHERE course_name = ? OR course_code = ?",
                        (app['preferred_course'], app['preferred_course'])
                    )
            conn.commit()
            return True

    def auto_shortlist(self) -> List[Dict]:
        """Auto-shortlist applications matching tariff requirements."""
        shortlisted = []
        with transaction() as conn:
            apps = conn.execute("SELECT * FROM clearing_applications WHERE status = 'pending'").fetchall()
            for app in apps:
                app_dict = dict(app)
                vacancies = conn.execute(
                    "SELECT * FROM clearing_vacancies WHERE is_active = 1 AND available_places > 0 AND minimum_tariff <= ? AND (course_name = ? OR course_code = ?)",
                    (app_dict['tariff_points'], app_dict.get('preferred_course', ''), app_dict.get('preferred_course', ''))
                ).fetchall()
                if vacancies:
                    conn.execute("UPDATE clearing_applications SET status = 'shortlisted' WHERE id = ?", (app_dict['id'],))
                    shortlisted.append(app_dict)
            conn.commit()
        return shortlisted

    def submit_adjustment_request(self, student_id: str, original_course: str, requested_course: str,
                                   reason: str = None, current_grades: str = None) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO adjustment_requests (student_id, original_course, requested_course, reason, current_grades) VALUES (?, ?, ?, ?, ?)",
                (student_id, original_course, requested_course, reason, current_grades)
            )
            conn.commit()
            return cursor.lastrowid

    def list_adjustment_requests(self, status: str = None) -> List[Dict]:
        with get_connection() as conn:
            if status:
                rows = conn.execute("SELECT * FROM adjustment_requests WHERE status = ? ORDER BY requested_at DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM adjustment_requests ORDER BY requested_at DESC").fetchall()
            return [dict(r) for r in rows]

    def process_adjustment(self, request_id: int, status: str, decided_by: str = None) -> bool:
        with transaction() as conn:
            conn.execute(
                "UPDATE adjustment_requests SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
                (status, decided_by, datetime.now().isoformat(), request_id)
            )
            conn.commit()
            return True

    def get_clearing_statistics(self) -> Dict:
        with get_connection() as conn:
            total_apps = conn.execute("SELECT COUNT(*) FROM clearing_applications").fetchone()[0]
            by_status = {}
            for row in conn.execute("SELECT status, COUNT(*) FROM clearing_applications GROUP BY status").fetchall():
                by_status[row[0]] = row[1]
            total_places = conn.execute("SELECT COALESCE(SUM(available_places), 0) FROM clearing_vacancies WHERE is_active = 1").fetchone()[0]
            return {"total_applications": total_apps, "by_status": by_status, "total_places_remaining": total_places}

    # --- GUI convenience aliases (map GUI-expected names to service methods) ---

    def get_vacancies(self, active_only: bool = True) -> List[Dict]:
        """Return vacancies with keys the GUI expects."""
        rows = self.list_vacancies(active_only=active_only)
        return [
            {
                "id": r["id"],
                "course": r.get("course_name", ""),
                "department": r.get("department", ""),
                "places": r.get("available_places", 0),
                "min_tariff": r.get("minimum_tariff", 0),
                "requirements": r.get("requirements", ""),
                "is_active": r.get("is_active", 1),
                "academic_year": r.get("academic_year", ""),
            }
            for r in rows
        ]

    def get_applications(self, status: str = None) -> List[Dict]:
        """Return applications with keys the GUI expects."""
        rows = self.list_applications(status=status)
        return [
            {
                "id": r["id"],
                "name": r.get("applicant_name", ""),
                "ucas_id": r.get("ucas_id", ""),
                "tariff": r.get("tariff_points", 0),
                "course": r.get("preferred_course", ""),
                "status": r.get("status", ""),
                "email": r.get("email", ""),
                "phone": r.get("phone", ""),
                "applied_at": r.get("applied_at", ""),
                "notes": r.get("notes", ""),
            }
            for r in rows
        ]

    def get_adjustments(self, status: str = None) -> List[Dict]:
        """Return adjustment requests with keys the GUI expects."""
        rows = self.list_adjustment_requests(status=status)
        return [
            {
                "id": r["id"],
                "student": r.get("student_id", ""),
                "original_course": r.get("original_course", ""),
                "requested_course": r.get("requested_course", ""),
                "reason": r.get("reason", ""),
                "current_grades": r.get("current_grades", ""),
                "status": r.get("status", ""),
                "requested_at": r.get("requested_at", ""),
            }
            for r in rows
        ]

    def get_statistics(self) -> Dict:
        """Return statistics with keys the GUI expects."""
        return self.get_clearing_statistics()
