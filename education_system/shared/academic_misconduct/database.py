"""Database operations for the Academic Misconduct Panel.

Includes chain-of-custody tracking, evidence tagging, and file hashing
(merged from the Evidence Organizer tool).
"""

import logging

from education_system.shared.academic_misconduct._imports import (
    sqlite3, DEFAULT_DB_PATH, datetime, compute_file_hash,
)

logger = logging.getLogger(__name__)


def init_misconduct_tables(db_path=None):
    """Create the academic misconduct tables if they don't exist."""
    db = str(db_path or DEFAULT_DB_PATH)
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        cursor = conn.cursor()

        # Main cases table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_misconduct_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT UNIQUE NOT NULL,
                system_key TEXT NOT NULL DEFAULT 'university',
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

        # Evidence table (enhanced with hash, category, notes from evidence organizer)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_misconduct_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT,
                file_size TEXT,
                file_hash TEXT DEFAULT '',
                category TEXT DEFAULT 'Document',
                notes TEXT DEFAULT '',
                uploaded_date TEXT NOT NULL,
                uploaded_by TEXT,
                FOREIGN KEY (case_id) REFERENCES academic_misconduct_cases(case_id)
            )
        ''')

        # Evidence tags (from evidence organizer)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_misconduct_evidence_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                FOREIGN KEY (evidence_id) REFERENCES academic_misconduct_evidence(id) ON DELETE CASCADE
            )
        ''')

        # Chain of custody (from evidence organizer)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_misconduct_chain_of_custody (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id INTEGER NOT NULL,
                handler TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT DEFAULT '',
                timestamp TEXT NOT NULL,
                FOREIGN KEY (evidence_id) REFERENCES academic_misconduct_evidence(id) ON DELETE CASCADE
            )
        ''')

        # Add columns to existing evidence tables if upgrading
        for col, typedef in [
            ("file_hash", "TEXT DEFAULT ''"),
            ("category", "TEXT DEFAULT 'Document'"),
            ("notes", "TEXT DEFAULT ''"),
        ]:
            try:
                cursor.execute(
                    f"ALTER TABLE academic_misconduct_evidence ADD COLUMN {col} {typedef}"
                )
            except Exception:
                pass  # Column already exists

        # Add system_key to cases table if upgrading from older schema
        try:
            cursor.execute(
                "ALTER TABLE academic_misconduct_cases ADD COLUMN system_key TEXT NOT NULL DEFAULT 'university'"
            )
        except Exception:
            pass  # Column already exists

        conn.commit()
    finally:
        conn.close()


class MisconductDatabaseMixin:
    """Mixin providing database operations for the misconduct panel."""

    def _get_db_path(self):
        """Return the misconduct-cases database path."""
        return str(getattr(self, '_db_path', None) or DEFAULT_DB_PATH)

    def _get_system_db_path(self):
        """Return the system-specific DB path for student / course lookups.

        Each education system stores its students in its own SQLite DB.
        This resolves the correct path based on ``self.system_key``.
        Falls back to ``_get_db_path()`` if the system isn't identifiable.
        """
        system_key = getattr(self, 'system_key', None)
        if system_key == 'university':
            try:
                from education_system.post_18.university_system.core.paths import (
                    DEFAULT_DB_PATH as _p,
                )
                return str(_p)
            except ImportError:
                pass
        # Fallback — use the misconduct DB (may contain student tables
        # if the system was launched within the university context).
        return self._get_db_path()

    def _system_key_filter(self):
        """Return (WHERE clause, params) for system_key filtering."""
        system_key = getattr(self, 'system_key', None)
        if system_key:
            return "WHERE system_key = ?", (system_key,)
        return "", ()

    def load_cases_from_db(self):
        """Load cases from the database, filtered by system_key if set."""
        conn = None
        try:
            conn = sqlite3.connect(self._get_db_path())
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            where, params = self._system_key_filter()
            # Pull source_record_id when present (column added by the
            # disciplinary portal's escalation flow). Use a tolerant
            # SELECT so older DBs without the column still work.
            try:
                cursor.execute(f'''
                    SELECT case_id, system_key, student_name, student_id, student_email, course,
                           violation_type, status, date_filed, severity, notes,
                           hearing_date, hearing_time, hearing_location, ruling, ruling_rationale,
                           source_record_id
                    FROM academic_misconduct_cases
                    {where}
                    ORDER BY date_filed DESC
                ''', params)
                rows = cursor.fetchall()
                has_source = True
            except sqlite3.OperationalError:
                cursor.execute(f'''
                    SELECT case_id, system_key, student_name, student_id, student_email, course,
                           violation_type, status, date_filed, severity, notes,
                           hearing_date, hearing_time, hearing_location, ruling, ruling_rationale
                    FROM academic_misconduct_cases
                    {where}
                    ORDER BY date_filed DESC
                ''', params)
                rows = cursor.fetchall()
                has_source = False

            self.cases = []
            for row in rows:
                self.cases.append({
                    'id': row['case_id'],
                    'system_key': row['system_key'],
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
                    'ruling_rationale': row['ruling_rationale'] or '',
                    'source_record_id':
                        (row['source_record_id'] if has_source else None),
                })
        except Exception as e:
            logger.warning("Error loading cases from database: %s", e)
            self.cases = []
        finally:
            if conn:
                conn.close()

    def refresh_dashboard(self):
        """Refresh the dashboard by reloading cases from database."""
        self.load_cases_from_db()
        self.populate_tree()
        if self.selected_case:
            self.refresh_evidence_tab()
        if hasattr(self, 'analytics_content'):
            self.refresh_analytics_tab()

    def save_case_to_db(self, case_data):
        """Save a new case to the database."""
        conn = None
        try:
            conn = sqlite3.connect(self._get_db_path())
            cursor = conn.cursor()
            # Use the panel's system_key, or fallback to case_data, or default 'university'
            sys_key = case_data.get('system_key') or getattr(self, 'system_key', None) or 'university'
            cursor.execute('''
                INSERT INTO academic_misconduct_cases
                (case_id, system_key, student_name, student_id, student_email, course, violation_type,
                 status, date_filed, severity, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                case_data['id'], sys_key, case_data['student'], case_data['student_id'],
                case_data.get('student_email', ''), case_data['course'], case_data['type'],
                case_data['status'], case_data['date_filed'], case_data['severity'],
                case_data['notes']
            ))

            cursor.execute('''
                INSERT INTO academic_misconduct_history (case_id, event_date, event_description, event_type)
                VALUES (?, ?, ?, ?)
            ''', (case_data['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  'Case filed', 'info'))

            conn.commit()
            return True
        except Exception as e:
            logger.warning("Error saving case to database: %s", e)
            return False
        finally:
            if conn:
                conn.close()

    def update_case_in_db(self, case_data):
        """Update an existing case in the database.

        Status propagation to the linked ``disciplinary_records`` row
        is handled by the DB-level trigger ``sync_misc_status_to_disc``
        installed by ``_db_init.ensure_disciplinary_schema`` — no
        application-side mirror needed here.
        """
        conn = None
        try:
            conn = sqlite3.connect(self._get_db_path())
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
            return True
        except Exception as e:
            logger.warning("Error updating case in database: %s", e)
            return False
        finally:
            if conn:
                conn.close()

    def delete_case_from_db(self, case_id):
        """Delete a case and all related records from the database."""
        conn = None
        try:
            conn = sqlite3.connect(self._get_db_path())
            conn.execute("PRAGMA foreign_keys=ON")
            cursor = conn.cursor()
            # Delete chain-of-custody and tags for evidence in this case
            cursor.execute('''
                DELETE FROM academic_misconduct_chain_of_custody
                WHERE evidence_id IN (
                    SELECT id FROM academic_misconduct_evidence WHERE case_id=?
                )
            ''', (case_id,))
            cursor.execute('''
                DELETE FROM academic_misconduct_evidence_tags
                WHERE evidence_id IN (
                    SELECT id FROM academic_misconduct_evidence WHERE case_id=?
                )
            ''', (case_id,))
            cursor.execute('DELETE FROM academic_misconduct_history WHERE case_id=?', (case_id,))
            cursor.execute('DELETE FROM academic_misconduct_evidence WHERE case_id=?', (case_id,))
            cursor.execute('DELETE FROM academic_misconduct_cases WHERE case_id=?', (case_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.warning("Error deleting case from database: %s", e)
            return False
        finally:
            if conn:
                conn.close()

    def add_case_history(self, case_id, description, event_type='info'):
        """Add an entry to case history."""
        conn = None
        try:
            conn = sqlite3.connect(self._get_db_path())
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO academic_misconduct_history (case_id, event_date, event_description, event_type)
                VALUES (?, ?, ?, ?)
            ''', (case_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), description, event_type))
            conn.commit()
        except Exception as e:
            logger.warning("Error adding case history: %s", e)
        finally:
            if conn:
                conn.close()

    def get_case_history(self, case_id):
        """Get history for a specific case."""
        conn = None
        try:
            conn = sqlite3.connect(self._get_db_path())
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT event_date, event_description, event_type
                FROM academic_misconduct_history
                WHERE case_id=?
                ORDER BY event_date DESC
            ''', (case_id,))
            rows = cursor.fetchall()
            return [(row['event_date'], row['event_description'], row['event_type']) for row in rows]
        except Exception as e:
            logger.warning("Error getting case history: %s", e)
            return []
        finally:
            if conn:
                conn.close()

    def get_next_case_id(self):
        """Generate the next case ID."""
        conn = None
        try:
            conn = sqlite3.connect(self._get_db_path())
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM academic_misconduct_cases')
            count = cursor.fetchone()[0]
            year = datetime.now().year
            return f"AMC-{year}-{str(count + 1).zfill(3)}"
        except Exception as e:
            logger.warning("Error generating next case ID: %s", e)
            year = datetime.now().year
            return f"AMC-{year}-{str(len(self.cases) + 1).zfill(3)}"
        finally:
            if conn:
                conn.close()

    # ------------------------------------------------------------------
    # Evidence chain-of-custody (merged from Evidence Organizer)
    # ------------------------------------------------------------------

    def add_chain_of_custody(self, evidence_id, handler, action, details=''):
        """Log a chain-of-custody entry for an evidence item."""
        conn = None
        try:
            conn = sqlite3.connect(self._get_db_path())
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO academic_misconduct_chain_of_custody
                (evidence_id, handler, action, details, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (evidence_id, handler, action, details,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
        except Exception as e:
            logger.warning("Error adding chain of custody: %s", e)
        finally:
            if conn:
                conn.close()

    def get_chain_of_custody(self, evidence_id):
        """Get chain-of-custody log for an evidence item."""
        conn = None
        try:
            conn = sqlite3.connect(self._get_db_path())
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT handler, action, details, timestamp
                FROM academic_misconduct_chain_of_custody
                WHERE evidence_id=?
                ORDER BY timestamp DESC
            ''', (evidence_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.warning("Error getting chain of custody: %s", e)
            return []
        finally:
            if conn:
                conn.close()

    # ------------------------------------------------------------------
    # Evidence tagging (merged from Evidence Organizer)
    # ------------------------------------------------------------------

    def add_evidence_tag(self, evidence_id, tag):
        """Add a tag to an evidence item."""
        conn = None
        try:
            conn = sqlite3.connect(self._get_db_path())
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO academic_misconduct_evidence_tags (evidence_id, tag)
                VALUES (?, ?)
            ''', (evidence_id, tag.strip()))
            conn.commit()
        except Exception as e:
            logger.warning("Error adding evidence tag: %s", e)
        finally:
            if conn:
                conn.close()

    def get_evidence_tags(self, evidence_id):
        """Get all tags for an evidence item."""
        conn = None
        try:
            conn = sqlite3.connect(self._get_db_path())
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tag FROM academic_misconduct_evidence_tags
                WHERE evidence_id=?
                ORDER BY tag
            ''', (evidence_id,))
            tags = [row[0] for row in cursor.fetchall()]
            return tags
        except Exception as e:
            logger.warning("Error getting evidence tags: %s", e)
            return []
        finally:
            if conn:
                conn.close()

    def remove_evidence_tag(self, evidence_id, tag):
        """Remove a tag from an evidence item."""
        conn = None
        try:
            conn = sqlite3.connect(self._get_db_path())
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM academic_misconduct_evidence_tags
                WHERE evidence_id=? AND tag=?
            ''', (evidence_id, tag))
            conn.commit()
        except Exception as e:
            logger.warning("Error removing evidence tag: %s", e)
        finally:
            if conn:
                conn.close()

    def verify_evidence_integrity(self, evidence_id):
        """Verify an evidence file's SHA-256 hash matches stored hash."""
        conn = None
        try:
            conn = sqlite3.connect(self._get_db_path())
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT file_path, file_hash FROM academic_misconduct_evidence
                WHERE id=?
            ''', (evidence_id,))
            row = cursor.fetchone()

            if not row or not row['file_path'] or not row['file_hash']:
                return None  # Cannot verify

            current_hash = compute_file_hash(row['file_path'])
            return current_hash == row['file_hash']
        except Exception as e:
            logger.warning("Error verifying evidence integrity: %s", e)
            return None
        finally:
            if conn:
                conn.close()
