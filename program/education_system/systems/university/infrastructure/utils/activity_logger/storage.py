import os
import gzip
import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

from education_system.systems.university.infrastructure.database.db import sqlite3

from education_system.systems.university.infrastructure.utils.activity_logger.models import LogEntry

_logger = logging.getLogger(__name__)


class LogRotationManager:
    """Handle log rotation and archival"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_size = config.get('max_file_size', 100 * 1024 * 1024)  # 100MB
        self.retention_days = config.get('retention_days', 30)
        self.compress_old_logs = config.get('compress_old_logs', True)

    def should_rotate(self, file_path: str) -> bool:
        """Check if log file should be rotated"""
        if not os.path.exists(file_path):
            return False

        file_size = os.path.getsize(file_path)
        return file_size >= self.max_size

    def rotate_log(self, file_path: str) -> str:
        """Rotate log file and return new filename"""
        if not os.path.exists(file_path):
            return file_path

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(file_path)[0]
        rotated_name = f"{base_name}_{timestamp}.log"

        # Move current log to rotated name
        os.rename(file_path, rotated_name)

        # Compress if enabled
        if self.compress_old_logs:
            self._compress_file(rotated_name)

        return file_path

    def _compress_file(self, file_path: str):
        """Compress log file using gzip"""
        compressed_path = f"{file_path}.gz"

        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                f_out.writelines(f_in)

        # Remove original file
        os.remove(file_path)

    def cleanup_old_logs(self, log_dir: str):
        """Remove logs older than retention period"""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        for file_path in Path(log_dir).glob("*.log*"):
            if file_path.stat().st_mtime < cutoff_date.timestamp():
                try:
                    file_path.unlink()
                    print(f"Removed old log file: {file_path}")
                except Exception as e:
                    print(f"Error removing log file {file_path}: {e}")

    def get_log_files_info(self, log_dir: str) -> List[Dict[str, Any]]:
        """Get information about log files in directory"""
        files_info = []

        for file_path in Path(log_dir).glob("*.log*"):
            stat = file_path.stat()
            files_info.append({
                'name': file_path.name,
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime),
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'compressed': file_path.suffix == '.gz'
            })

        return sorted(files_info, key=lambda x: x['modified'], reverse=True)


class DatabaseManager:
    """Manage database connections and operations"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()

    def get_connection(self):
        """Get a database connection"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = OFF")
        return conn

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute a SELECT query and return results"""
        with self._lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = [dict(row) for row in cursor.fetchall()]
                return results
            finally:
                conn.close()

    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows"""
        with self._lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()

    def execute_batch(self, query: str, params_list: List[tuple]) -> int:
        """Execute batch operations"""
        with self._lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()


class DatabaseLogger:
    """Handle database logging operations using the main activity_log table."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        self.db_manager.get_connection().close()

    def _build_details(self, log_entry: LogEntry) -> str:
        """Pack extra log fields into a JSON details string."""
        detail_parts = {}
        if log_entry.details:
            detail_parts['message'] = log_entry.details
        for field in ('role', 'module', 'status', 'log_level', 'session_id',
                       'user_agent', 'request_size', 'response_size',
                       'processing_time', 'geolocation', 'security_level',
                       'trace_id', 'stack_trace'):
            val = getattr(log_entry, field, None)
            if val is not None:
                detail_parts[field] = val
        if log_entry.metadata:
            detail_parts['metadata'] = log_entry.metadata
        return json.dumps(detail_parts) if detail_parts else None

    def insert_log(self, log_entry: LogEntry):
        """Insert log entry into the activity_log table."""
        query = '''
            INSERT INTO activity_log (
                user_id, username, action, details, timestamp, ip_address
            ) VALUES (?, ?, ?, ?, ?, ?)
        '''
        params = (
            log_entry.user_id, log_entry.username, log_entry.action,
            self._build_details(log_entry), log_entry.timestamp,
            log_entry.ip_address,
        )
        self.db_manager.execute_update(query, params)

    def insert_batch_logs(self, log_entries: List[LogEntry]):
        """Insert multiple log entries in batch."""
        query = '''
            INSERT INTO activity_log (
                user_id, username, action, details, timestamp, ip_address
            ) VALUES (?, ?, ?, ?, ?, ?)
        '''
        params_list = [
            (
                e.user_id, e.username, e.action,
                self._build_details(e), e.timestamp,
                e.ip_address,
            )
            for e in log_entries
        ]
        self.db_manager.execute_batch(query, params_list)

    def query_logs(self, filters: Dict[str, Any] = None, limit: int = 1000) -> List[Dict]:
        """Query logs with optional filters."""
        query = "SELECT * FROM activity_log"
        params = []

        if filters:
            conditions = []
            for key, value in filters.items():
                if key == 'timestamp_from':
                    conditions.append("timestamp >= ?")
                    params.append(value)
                elif key == 'timestamp_to':
                    conditions.append("timestamp <= ?")
                    params.append(value)
                elif key == 'date_from':
                    conditions.append("DATE(timestamp) >= ?")
                    params.append(value)
                elif key == 'date_to':
                    conditions.append("DATE(timestamp) <= ?")
                    params.append(value)
                elif isinstance(value, list):
                    placeholders = ','.join(['?' for _ in value])
                    conditions.append(f"{key} IN ({placeholders})")
                    params.extend(value)
                else:
                    conditions.append(f"{key} = ?")
                    params.append(value)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        query += f" ORDER BY timestamp DESC LIMIT {limit}"

        return self.db_manager.execute_query(query, tuple(params))

    def get_log_count(self, filters: Dict[str, Any] = None) -> int:
        """Get count of logs matching filters."""
        query = "SELECT COUNT(*) as count FROM activity_log"
        params = []

        if filters:
            conditions = []
            for key, value in filters.items():
                if key == 'timestamp_from':
                    conditions.append("timestamp >= ?")
                    params.append(value)
                elif key == 'timestamp_to':
                    conditions.append("timestamp <= ?")
                    params.append(value)
                elif isinstance(value, list):
                    placeholders = ','.join(['?' for _ in value])
                    conditions.append(f"{key} IN ({placeholders})")
                    params.extend(value)
                else:
                    conditions.append(f"{key} = ?")
                    params.append(value)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        result = self.db_manager.execute_query(query, tuple(params))
        return result[0]['count'] if result else 0

    def delete_old_logs(self, days: int) -> int:
        """Delete logs older than specified days."""
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        query = "DELETE FROM activity_log WHERE timestamp < ?"
        return self.db_manager.execute_update(query, (cutoff_date,))

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        stats = {}

        # Total logs
        stats['total_logs'] = self.get_log_count()

        # Recent activity (last 24 hours)
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        stats['recent_activity'] = self.get_log_count({'timestamp_from': yesterday})

        # Database size
        try:
            stats['database_size'] = os.path.getsize(self.db_path)
        except (OSError, FileNotFoundError) as e:
            _logger.warning(f"Failed to get database size: {e}")
            stats['database_size'] = 0

        return stats
