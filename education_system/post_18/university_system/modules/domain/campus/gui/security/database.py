"""Database schema, initialization, and CRUD operations for the Campus Public Safety system."""

import json
import logging

from education_system.post_18.university_system.core.sql_safety import validate_table_name

logger = logging.getLogger(__name__)

# Database schema for campus public safety tables
POLICE_STATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS police_cases (
    id TEXT PRIMARY KEY,
    title TEXT,
    type TEXT,
    status TEXT DEFAULT 'Open',
    priority TEXT DEFAULT 'Medium',
    officer TEXT,
    location TEXT,
    description TEXT,
    notes TEXT,
    witnesses TEXT,
    student_id TEXT,
    student_name TEXT,
    is_student_involved INTEGER DEFAULT 0,
    date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_officers (
    badge TEXT PRIMARY KEY,
    name TEXT,
    rank TEXT,
    department TEXT,
    status TEXT DEFAULT 'Active',
    phone TEXT,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_complaints (
    id TEXT PRIMARY KEY,
    complainant TEXT,
    email TEXT,
    phone TEXT,
    student_id TEXT,
    is_student INTEGER DEFAULT 0,
    type TEXT,
    priority TEXT DEFAULT 'Medium',
    status TEXT DEFAULT 'Pending',
    incident_date TEXT,
    incident_time TEXT,
    location TEXT,
    description TEXT,
    suspect_description TEXT,
    date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_criminals (
    id TEXT PRIMARY KEY,
    name TEXT,
    student_id TEXT,
    is_student INTEGER DEFAULT 0,
    affiliation TEXT,
    crime TEXT,
    status TEXT,
    arrest_date TEXT,
    case_number TEXT,
    description TEXT,
    trespass_notice INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_evidence (
    id TEXT PRIMARY KEY,
    description TEXT,
    case_number TEXT,
    type TEXT,
    location TEXT,
    custody TEXT,
    date_added TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_patrol_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    officer TEXT,
    area TEXT,
    start_time TEXT,
    end_time TEXT,
    status TEXT,
    notes TEXT,
    date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_emergency_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    location TEXT,
    details TEXT,
    reporter TEXT,
    timestamp TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_police_database():
    """Initialize police station database tables."""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            conn.executescript(POLICE_STATION_SCHEMA)
            conn.commit()
        logger.info("Police station database tables initialized")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize police database: {e}")
        return False


class DatabaseMixin:
    """Mixin providing all database load/save/delete operations for PoliceStationApp."""

    def load_data(self):
        """Load data from database"""
        # Initialize database tables
        init_police_database()

        # Load data from database
        self.data = {
            "cases": self._db_load_cases(),
            "officers": self._db_load_officers(),
            "complaints": self._db_load_complaints(),
            "criminals": self._db_load_criminals(),
            "evidence": self._db_load_evidence(),
            "patrol_logs": self._db_load_patrol_logs(),
            "emergency_alerts": self._db_load_emergency_alerts()
        }

    def _db_load_cases(self):
        """Load cases from database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM police_cases ORDER BY date DESC")
                rows = cursor.fetchall()
                cases = []
                for row in rows:
                    case = dict(row)
                    # Parse witnesses JSON
                    if case.get('witnesses'):
                        try:
                            case['witnesses'] = json.loads(case['witnesses'])
                        except (ValueError, json.JSONDecodeError):
                            case['witnesses'] = []
                    else:
                        case['witnesses'] = []
                    cases.append(case)
                return cases
        except Exception as e:
            logger.error(f"Failed to load cases: {e}")
            return []

    def _db_load_officers(self):
        """Load officers from database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM police_officers ORDER BY name")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to load officers: {e}")
            return []

    def _db_load_complaints(self):
        """Load complaints from database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM police_complaints ORDER BY date DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to load complaints: {e}")
            return []

    def _db_load_criminals(self):
        """Load criminal records from database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM police_criminals ORDER BY name")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to load criminals: {e}")
            return []

    def _db_load_evidence(self):
        """Load evidence from database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM police_evidence ORDER BY date_added DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to load evidence: {e}")
            return []

    def _db_load_patrol_logs(self):
        """Load patrol logs from database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM police_patrol_logs ORDER BY date DESC, start_time DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to load patrol logs: {e}")
            return []

    def _db_load_emergency_alerts(self):
        """Load emergency alerts from database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM police_emergency_alerts ORDER BY timestamp DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to load emergency alerts: {e}")
            return []

    def save_data(self):
        """Refresh data from database (data is saved immediately on each operation)."""
        # Data is saved immediately on each operation, so just reload
        pass

    def _db_save_case(self, case):
        """Save a case to database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            witnesses_json = json.dumps(case.get('witnesses', []))
            with get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO police_cases
                    (id, title, type, status, priority, officer, location, description, notes, witnesses, date, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (case.get('id'), case.get('title'), case.get('type'), case.get('status'),
                      case.get('priority'), case.get('officer'), case.get('location'),
                      case.get('description'), case.get('notes'), witnesses_json, case.get('date')))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save case: {e}")
            return False

    def _db_delete_case(self, case_id):
        """Delete a case from database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM police_cases WHERE id = ?", (case_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete case: {e}")
            return False

    def _db_save_officer(self, officer):
        """Save an officer to database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO police_officers
                    (badge, name, rank, department, status, phone, email)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (officer.get('badge'), officer.get('name'), officer.get('rank'),
                      officer.get('department'), officer.get('status'), officer.get('phone'),
                      officer.get('email')))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save officer: {e}")
            return False

    def _db_delete_officer(self, badge):
        """Delete an officer from database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM police_officers WHERE badge = ?", (badge,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete officer: {e}")
            return False

    def _db_save_complaint(self, complaint):
        """Save a complaint to database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO police_complaints
                    (id, complainant, email, phone, type, priority, status, incident_date,
                     incident_time, location, description, suspect_description, date, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (complaint.get('id'), complaint.get('complainant'), complaint.get('email'),
                      complaint.get('phone'), complaint.get('type'), complaint.get('priority'),
                      complaint.get('status'), complaint.get('incident_date'), complaint.get('incident_time'),
                      complaint.get('location'), complaint.get('description'),
                      complaint.get('suspect_description'), complaint.get('date')))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save complaint: {e}")
            return False

    def _db_delete_complaint(self, complaint_id):
        """Delete a complaint from database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM police_complaints WHERE id = ?", (complaint_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete complaint: {e}")
            return False

    def _db_save_criminal(self, criminal):
        """Save a criminal record to database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO police_criminals
                    (id, name, crime, status, arrest_date, case_number, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (criminal.get('id'), criminal.get('name'), criminal.get('crime'),
                      criminal.get('status'), criminal.get('arrest_date'),
                      criminal.get('case_number'), criminal.get('description')))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save criminal: {e}")
            return False

    def _db_delete_criminal(self, criminal_id):
        """Delete a criminal record from database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM police_criminals WHERE id = ?", (criminal_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete criminal: {e}")
            return False

    def _db_save_evidence(self, evidence):
        """Save evidence to database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO police_evidence
                    (id, description, case_number, type, location, custody, date_added)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (evidence.get('id'), evidence.get('description'), evidence.get('case_number'),
                      evidence.get('type'), evidence.get('location'), evidence.get('custody'),
                      evidence.get('date_added')))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save evidence: {e}")
            return False

    def _db_delete_evidence(self, evidence_id):
        """Delete evidence from database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM police_evidence WHERE id = ?", (evidence_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete evidence: {e}")
            return False

    def _db_save_patrol_log(self, log):
        """Save a patrol log to database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""
                    INSERT INTO police_patrol_logs
                    (officer, area, start_time, end_time, status, notes, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (log.get('officer'), log.get('area'), log.get('start_time'),
                      log.get('end_time'), log.get('status'), log.get('notes'), log.get('date')))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save patrol log: {e}")
            return False

    def _db_delete_patrol_log(self, date, officer):
        """Delete a patrol log from database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM police_patrol_logs WHERE date = ? AND officer = ?", (date, officer))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete patrol log: {e}")
            return False

    def _db_save_emergency_alert(self, alert):
        """Save an emergency alert to database."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""
                    INSERT INTO police_emergency_alerts
                    (type, location, details, reporter, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (alert.get('type'), alert.get('location'), alert.get('details'),
                      alert.get('reporter'), alert.get('timestamp')))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save emergency alert: {e}")
            return False

    def _db_get_next_id(self, prefix, table, id_column='id'):
        """Get the next ID for a table."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            safe_table = validate_table_name(table)
            with get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM [" + safe_table + "]")
                count = cursor.fetchone()[0]
                return f"{prefix}{count + 1:04d}"
        except Exception as e:
            logger.error(f"Failed to get next ID: {e}")
            return f"{prefix}0001"
