"""External examiner visit tracking and action log service."""

from datetime import datetime
from typing import Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction


class ExternalExaminerService:
    """Service for tracking external examiner visits and action items."""

    def __init__(self):
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        with transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS external_examiners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT,
                    institution TEXT,
                    specialisation TEXT,
                    appointment_start TEXT,
                    appointment_end TEXT,
                    status TEXT DEFAULT 'active'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS examiner_visits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    examiner_id INTEGER NOT NULL,
                    visit_date TEXT NOT NULL,
                    department TEXT,
                    purpose TEXT,
                    modules_reviewed TEXT,
                    findings TEXT,
                    recommendations TEXT,
                    overall_rating TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (examiner_id) REFERENCES external_examiners(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS examiner_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    visit_id INTEGER,
                    action_description TEXT NOT NULL,
                    responsible_person TEXT,
                    deadline TEXT,
                    status TEXT DEFAULT 'pending',
                    completed_at TEXT,
                    notes TEXT,
                    FOREIGN KEY (visit_id) REFERENCES examiner_visits(id)
                )
            """)
            conn.commit()

    def add_examiner(self, name: str = None, email: str = None, institution: str = None,
                     specialisation: str = None, appointment_start: str = None,
                     appointment_end: str = None, **kwargs) -> int:
        # Accept dict or keyword args
        if isinstance(name, dict):
            data = name
            name = data.get('name', '')
            email = data.get('email')
            institution = data.get('institution')
            specialisation = data.get('specialisation') or data.get('expertise_area')
            appointment_start = data.get('appointment_start')
            appointment_end = data.get('appointment_end')

        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO external_examiners (name, email, institution, specialisation, appointment_start, appointment_end) VALUES (?, ?, ?, ?, ?, ?)",
                (name, email, institution, specialisation, appointment_start, appointment_end)
            )
            conn.commit()
            return cursor.lastrowid

    def get_examiner(self, examiner_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM external_examiners WHERE id = ?", (examiner_id,)).fetchone()
            return dict(row) if row else None

    def list_examiners(self, status: str = None) -> List[Dict]:
        with get_connection() as conn:
            if status:
                rows = conn.execute("SELECT * FROM external_examiners WHERE status = ?", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM external_examiners ORDER BY name").fetchall()
            return [dict(r) for r in rows]

    def update_examiner(self, examiner_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        from education_system.shared.database.sql_safety import validate_identifier  # nosec B608
        sets = ", ".join(f"{validate_identifier(k)} = ?" for k in kwargs)
        with transaction() as conn:
            conn.execute(f"UPDATE external_examiners SET {sets} WHERE id = ?", (*kwargs.values(), examiner_id))
            conn.commit()
            return True

    def schedule_visit(self, examiner_id=None, visit_date: str = None, department: str = None,
                       purpose: str = None, created_by: str = None, **kwargs) -> int:
        # Accept dict as first argument
        if isinstance(examiner_id, dict):
            data = examiner_id
            examiner_id = data.get('examiner_id') or data.get('examiner')
            visit_date = data.get('visit_date') or data.get('date')
            department = data.get('department')
            purpose = data.get('purpose') or data.get('rating', '')
            created_by = data.get('created_by')

        import sqlite3 as _sqlite3
        from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH
        conn = _sqlite3.connect(str(DEFAULT_DB_PATH))
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
            cursor = conn.execute(
                "INSERT INTO examiner_visits (examiner_id, visit_date, department, purpose, created_by) VALUES (?, ?, ?, ?, ?)",
                (examiner_id, visit_date, department, purpose, created_by)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_visit(self, visit_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM examiner_visits WHERE id = ?", (visit_id,)).fetchone()
            return dict(row) if row else None

    def list_visits(self, examiner_id: int = None) -> List[Dict]:
        with get_connection() as conn:
            if examiner_id:
                rows = conn.execute("SELECT * FROM examiner_visits WHERE examiner_id = ? ORDER BY visit_date DESC", (examiner_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM examiner_visits ORDER BY visit_date DESC").fetchall()
            return [dict(r) for r in rows]

    def record_findings(self, visit_id=None, findings: str = None, recommendations=None,
                        overall_rating: str = None) -> bool:
        # Handle GUI calling with (visit_id, examiner_name, {dict})
        if isinstance(recommendations, dict):
            data = recommendations
            overall_rating = data.get('rating', overall_rating)
            findings = data.get('findings', findings)
            recommendations = data.get('recommendations')

        with transaction() as conn:
            conn.execute(
                "UPDATE examiner_visits SET findings = ?, recommendations = ?, overall_rating = ? WHERE id = ?",
                (findings, recommendations, overall_rating, visit_id)
            )
            conn.commit()
            return True

    def add_action_item(self, visit_id=None, action_description: str = None,
                        responsible_person: str = None, deadline: str = None, **kwargs) -> int:
        # Accept dict as first argument
        if isinstance(visit_id, dict):
            data = visit_id
            visit_id = data.get('visit_id')
            action_description = data.get('action_description') or data.get('description')
            responsible_person = data.get('responsible_person') or data.get('responsible')
            deadline = data.get('deadline')

        # If no visit_id, use the most recent visit (if any)
        if not visit_id:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT id FROM examiner_visits ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                visit_id = row[0] if row else None

        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO examiner_actions (visit_id, action_description, responsible_person, deadline) VALUES (?, ?, ?, ?)",
                (visit_id, action_description, responsible_person, deadline)
            )
            conn.commit()
            return cursor.lastrowid

    def update_action_status(self, action_id: int, status: str) -> bool:
        with transaction() as conn:
            completed_at = datetime.now().isoformat() if status == 'completed' else None
            conn.execute(
                "UPDATE examiner_actions SET status = ?, completed_at = ? WHERE id = ?",
                (status, completed_at, action_id)
            )
            conn.commit()
            return True

    def get_actions_by_visit(self, visit_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM examiner_actions WHERE visit_id = ? ORDER BY deadline", (visit_id,)).fetchall()
            return [dict(r) for r in rows]

    def list_actions(self) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM examiner_actions ORDER BY deadline"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_overdue_actions(self) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM examiner_actions WHERE status != 'completed' AND deadline < ? ORDER BY deadline",
                (datetime.now().strftime('%Y-%m-%d'),)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_examiner_history(self, examiner_id: int) -> Dict:
        with get_connection() as conn:
            visits = self.list_visits(examiner_id)
            examiner = self.get_examiner(examiner_id)
            return {"examiner": examiner, "visits": visits, "total_visits": len(visits)}

    def get_department_summary(self, department: str = None) -> List[Dict]:
        with get_connection() as conn:
            if department:
                rows = conn.execute(
                    "SELECT department, COUNT(*) as visit_count, MAX(visit_date) as last_visit FROM examiner_visits WHERE department = ? GROUP BY department",
                    (department,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT department, COUNT(*) as visit_count, MAX(visit_date) as last_visit FROM examiner_visits GROUP BY department ORDER BY department"
                ).fetchall()
            return [dict(r) for r in rows]
