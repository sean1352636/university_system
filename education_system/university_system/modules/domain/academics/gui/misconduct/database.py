"""Database operations for the Academic Misconduct Panel."""

from ._imports import sqlite3, DEFAULT_DB_PATH, datetime


def init_misconduct_tables():
    """Create the academic misconduct tables if they don't exist."""
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    # Main cases table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academic_misconduct_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT UNIQUE NOT NULL,
            student_name TEXT NOT NULL,
            student_id TEXT NOT NULL,
            student_email TEXT,
            course TEXT NOT NULL,
            violation_type TEXT NOT NULL,
            status TEXT DEFAULT 'Under Review',
            date_filed TEXT NOT NULL,
            severity TEXT NOT NULL,
            notes TEXT,
            hearing_date TEXT,
            hearing_time TEXT,
            hearing_location TEXT,
            ruling TEXT,
            ruling_rationale TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Case history/timeline table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academic_misconduct_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_description TEXT NOT NULL,
            event_type TEXT DEFAULT 'info',
            created_by TEXT,
            FOREIGN KEY (case_id) REFERENCES academic_misconduct_cases(case_id)
        )
    ''')

    # Evidence table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academic_misconduct_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT,
            file_size TEXT,
            uploaded_date TEXT NOT NULL,
            uploaded_by TEXT,
            FOREIGN KEY (case_id) REFERENCES academic_misconduct_cases(case_id)
        )
    ''')

    conn.commit()
    conn.close()


class MisconductDatabaseMixin:
    """Mixin providing database operations for the misconduct panel."""

    def load_cases_from_db(self):
        """Load all cases from the database."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT case_id, student_name, student_id, student_email, course,
                       violation_type, status, date_filed, severity, notes,
                       hearing_date, hearing_time, hearing_location, ruling, ruling_rationale
                FROM academic_misconduct_cases
                ORDER BY date_filed DESC
            ''')
            rows = cursor.fetchall()
            conn.close()

            self.cases = []
            for row in rows:
                self.cases.append({
                    'id': row['case_id'],
                    'student': row['student_name'],
                    'student_id': row['student_id'],
                    'student_email': row['student_email'] or '',
                    'course': row['course'],
                    'type': row['violation_type'],
                    'status': row['status'],
                    'date_filed': row['date_filed'],
                    'severity': row['severity'],
                    'notes': row['notes'] or '',
                    'hearing_date': row['hearing_date'] or '',
                    'hearing_time': row['hearing_time'] or '',
                    'hearing_location': row['hearing_location'] or '',
                    'ruling': row['ruling'] or '',
                    'ruling_rationale': row['ruling_rationale'] or ''
                })
        except Exception as e:
            print(f"Error loading cases from database: {e}")
            self.cases = []

    def refresh_dashboard(self):
        """Refresh the dashboard by reloading cases from database."""
        self.load_cases_from_db()
        self.populate_tree()
        # Also refresh tabs if a case is selected
        if self.selected_case:
            self.refresh_evidence_tab()
        # Always refresh analytics (global data)
        if hasattr(self, 'analytics_content'):
            self.refresh_analytics_tab()

    def save_case_to_db(self, case_data):
        """Save a new case to the database."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO academic_misconduct_cases
                (case_id, student_name, student_id, student_email, course, violation_type,
                 status, date_filed, severity, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                case_data['id'], case_data['student'], case_data['student_id'],
                case_data.get('student_email', ''), case_data['course'], case_data['type'],
                case_data['status'], case_data['date_filed'], case_data['severity'],
                case_data['notes']
            ))

            # Add to history
            cursor.execute('''
                INSERT INTO academic_misconduct_history (case_id, event_date, event_description, event_type)
                VALUES (?, ?, ?, ?)
            ''', (case_data['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  'Case filed', 'info'))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving case to database: {e}")
            return False

    def update_case_in_db(self, case_data):
        """Update an existing case in the database."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE academic_misconduct_cases
                SET student_name=?, student_id=?, student_email=?, course=?, violation_type=?,
                    status=?, severity=?, notes=?, hearing_date=?, hearing_time=?,
                    hearing_location=?, ruling=?, ruling_rationale=?, updated_at=CURRENT_TIMESTAMP
                WHERE case_id=?
            ''', (
                case_data['student'], case_data['student_id'], case_data.get('student_email', ''),
                case_data['course'], case_data['type'], case_data['status'], case_data['severity'],
                case_data['notes'], case_data.get('hearing_date', ''), case_data.get('hearing_time', ''),
                case_data.get('hearing_location', ''), case_data.get('ruling', ''),
                case_data.get('ruling_rationale', ''), case_data['id']
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating case in database: {e}")
            return False

    def delete_case_from_db(self, case_id):
        """Delete a case from the database."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('DELETE FROM academic_misconduct_history WHERE case_id=?', (case_id,))
            cursor.execute('DELETE FROM academic_misconduct_evidence WHERE case_id=?', (case_id,))
            cursor.execute('DELETE FROM academic_misconduct_cases WHERE case_id=?', (case_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error deleting case from database: {e}")
            return False

    def add_case_history(self, case_id, description, event_type='info'):
        """Add an entry to case history."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO academic_misconduct_history (case_id, event_date, event_description, event_type)
                VALUES (?, ?, ?, ?)
            ''', (case_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), description, event_type))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error adding case history: {e}")

    def get_case_history(self, case_id):
        """Get history for a specific case."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT event_date, event_description, event_type
                FROM academic_misconduct_history
                WHERE case_id=?
                ORDER BY event_date DESC
            ''', (case_id,))
            rows = cursor.fetchall()
            conn.close()
            return [(row['event_date'], row['event_description'], row['event_type']) for row in rows]
        except Exception as e:
            print(f"Error getting case history: {e}")
            return []

    def get_next_case_id(self):
        """Generate the next case ID."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM academic_misconduct_cases')
            count = cursor.fetchone()[0]
            conn.close()
            year = datetime.now().year
            return f"AMC-{year}-{str(count + 1).zfill(3)}"
        except Exception:
            year = datetime.now().year
            return f"AMC-{year}-{str(len(self.cases) + 1).zfill(3)}"
