import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple
from education_system.university_system.utils.logging.log_config import configure_logging
from education_system.university_system.modules.domain.academics.services.academic_calendar.config import ValidationUtils

logger = configure_logging(name=__name__)


class AuditManager:
    """Manages audit trail and change tracking"""

    def __init__(self, db_manager):
        self.db_manager = db_manager
        self._ensure_audit_table()

    def _ensure_audit_table(self):
        """Ensure audit_log table exists with proper schema"""
        try:
            # Check if audit_log table exists and get its schema
            rows = self.db_manager.execute_query(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='audit_log'"
            )

            if not rows:
                # Table doesn't exist, create it
                self._create_audit_table()
            else:
                # Table exists, check if it has id column
                schema = rows[0][0].lower() if rows[0][0] else ""
                if 'id' not in schema or 'primary key' not in schema:
                    # Try to add id column if missing
                    try:
                        self.db_manager.execute_update(
                            "ALTER TABLE audit_log ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT"
                        )
                        logging.info("Added id column to existing audit_log table")
                    except Exception as e:
                        logging.warning(f"Could not add id column to audit_log: {e}")
                        # Continue without id column

        except Exception as e:
            logging.warning(f"Could not ensure audit table: {e}")

    def _create_audit_table(self):
        """Create audit_log table with proper schema"""
        try:
            self.db_manager.execute_update('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    old_values TEXT,
                    new_values TEXT,
                    user_id TEXT,
                    timestamp TEXT NOT NULL,
                    ip_address TEXT
                )
            ''')
            logging.info("Created audit_log table")
        except Exception as e:
            logging.error(f"Failed to create audit_log table: {e}")

    def log_change(self, table_name: str, record_id: str, action: str,
                  old_values: Dict = None, new_values: Dict = None,
                  user_id: str = None, ip_address: str = None) -> Tuple[bool, str]:
        """Log a change to the audit trail with fallback for missing id column"""
        try:
            # Check what columns exist in the audit_log table
            rows = self.db_manager.execute_query("PRAGMA table_info(audit_log)")
            columns = [row[1] for row in rows]  # row[1] is column name

            # Sanitize inputs
            table_name = ValidationUtils.sanitize_string(table_name, 50)
            record_id = ValidationUtils.sanitize_string(record_id, 100)
            action = ValidationUtils.sanitize_string(action, 20)
            timestamp = datetime.now().isoformat()

            if 'id' in columns:
                # Table has id column, use it
                self.db_manager.execute_update('''
                    INSERT INTO audit_log (table_name, record_id, action, old_values,
                           new_values, user_id, timestamp, ip_address)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    table_name, record_id, action,
                    json.dumps(old_values) if old_values else None,
                    json.dumps(new_values) if new_values else None,
                    user_id, timestamp, ip_address
                ))
            else:
                # Table doesn't have id column, insert without it
                available_columns = ['table_name', 'record_id', 'action', 'timestamp']
                values = [table_name, record_id, action, timestamp]

                # Add optional columns if they exist
                if 'old_values' in columns and old_values:
                    available_columns.append('old_values')
                    values.append(json.dumps(old_values))

                if 'new_values' in columns and new_values:
                    available_columns.append('new_values')
                    values.append(json.dumps(new_values))

                if 'user_id' in columns and user_id:
                    available_columns.append('user_id')
                    values.append(user_id)

                if 'ip_address' in columns and ip_address:
                    available_columns.append('ip_address')
                    values.append(ip_address)

                # Build and execute query
                placeholders = ', '.join(['?'] * len(values))
                column_names = ', '.join(available_columns)

                self.db_manager.execute_update(
                    f"INSERT INTO audit_log ({column_names}) VALUES ({placeholders})",
                    tuple(values)
                )

            return True, "Change logged successfully"

        except Exception as e:
            logging.error(f"Failed to log audit entry: {e}")
            # Don't fail the main operation if audit logging fails
            return False, f"Failed to log change: {str(e)}"

    def get_audit_trail(self, table_name: str = None, record_id: str = None,
                       user_id: str = None, limit: int = 100) -> Tuple[bool, List[Dict]]:
        """Retrieve audit trail with optional filters"""
        try:
            query = "SELECT * FROM audit_log"
            conditions = []
            params = []

            if table_name:
                conditions.append("table_name = ?")
                params.append(ValidationUtils.sanitize_string(table_name, 50))

            if record_id:
                conditions.append("record_id = ?")
                params.append(ValidationUtils.sanitize_string(record_id, 100))

            if user_id:
                conditions.append("user_id = ?")
                params.append(user_id)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(min(limit, 1000))  # Cap at 1000 records

            rows = self.db_manager.execute_query(query, tuple(params))
            results = [dict(row) for row in rows]

            return True, results

        except Exception as e:
            logging.error(f"Failed to retrieve audit trail: {e}")
            return False, []
