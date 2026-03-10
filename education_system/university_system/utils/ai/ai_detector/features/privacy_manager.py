"""Privacy controls and compliance management."""

import hashlib
from datetime import datetime
from typing import Dict, List

from education_system.university_system.utils.ai.ai_detector.core.constants import logger


class PrivacyManager:
    """Manages privacy controls and compliance"""

    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.consent_records = {}

    def initialize_privacy_tables(self):
        """Initialize privacy-related database tables"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()

            # Privacy consent table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS privacy_consent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                consent_type TEXT NOT NULL,
                granted INTEGER NOT NULL,
                granted_at TEXT NOT NULL,
                expires_at TEXT,
                version TEXT NOT NULL,
                UNIQUE(student_id, consent_type)
            )
            ''')

            # Data retention table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_retention (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_type TEXT NOT NULL,
                retention_period INTEGER NOT NULL,
                deletion_date TEXT,
                status TEXT DEFAULT 'active'
            )
            ''')

            # Audit log table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS privacy_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                student_id TEXT,
                user_id INTEGER,
                data_accessed TEXT,
                timestamp TEXT NOT NULL,
                ip_address TEXT
            )
            ''')

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error initializing privacy tables: {e}")

    def check_consent(self, student_id: str, consent_type: str) -> bool:
        """Check if student has given consent for specific data processing"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT granted, expires_at
            FROM privacy_consent
            WHERE student_id = ? AND consent_type = ?
            ''', (student_id, consent_type))

            result = cursor.fetchone()
            conn.close()

            if not result:
                return False

            granted, expires_at = result

            if not granted:
                return False

            # Check if consent has expired
            if expires_at:
                expiry_date = datetime.fromisoformat(expires_at)
                if datetime.now() > expiry_date:
                    return False

            return True

        except Exception as e:
            logger.error(f"Error checking consent: {e}")
            return False

    def record_data_access(self, action: str, student_id: str = None, data_accessed: str = None):
        """Record data access for audit purposes"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()

            user_id = self.detector.current_user.get('id') if self.detector.current_user else None

            cursor.execute('''
            INSERT INTO privacy_audit_log
            (action, student_id, user_id, data_accessed, timestamp)
            VALUES (?, ?, ?, ?, ?)
            ''', (action, student_id, user_id, data_accessed, datetime.now().isoformat()))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error recording data access: {e}")

    def anonymize_data(self, data: Dict, fields_to_anonymize: List[str]) -> Dict:
        """Anonymize sensitive data fields"""
        anonymized = data.copy()

        for field in fields_to_anonymize:
            if field in anonymized:
                if field == 'student_id':
                    # Hash student ID
                    anonymized[field] = hashlib.sha256(str(data[field]).encode()).hexdigest()[:8]
                elif field in ['ip_address', 'device_fingerprint']:
                    # Partial anonymization
                    value = str(data[field])
                    if len(value) > 4:
                        anonymized[field] = value[:4] + '*' * (len(value) - 4)
                else:
                    # Full anonymization
                    anonymized[field] = '[ANONYMIZED]'

        return anonymized
