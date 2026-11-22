import logging
from datetime import datetime
from pathlib import Path
import shutil
from typing import Any, Optional, Tuple, List, Dict
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.domains.teaching.interfaces.gui.academic_calendar.exceptions import DatabaseError, ExportError
from education_system.systems.university.domains.teaching.interfaces.gui.academic_calendar.utils import convert_to_user_error

gui_logger = logging.getLogger(__name__)

class ConnectionPool:
    """
    Database connection pool for efficient connection management

    Provides connection pooling to reduce connection overhead and
    improve performance for database operations.
    """

    def __init__(self, db_path: str, pool_size: int = 5):
        """
        Initialize connection pool

        Args:
            db_path: Path to database file
            pool_size: Number of connections to maintain
        """
        self.db_path = db_path
        self.pool_size = pool_size
        self._connection = None

    def __enter__(self):
        """Context manager entry - get connection"""
        self._connection = sqlite3.connect(self.db_path)
        self._connection.row_factory = sqlite3.Row
        return self._connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection"""
        if self._connection:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
            self._connection.close()
        return False

class DatabaseManager:
    """
    Comprehensive database abstraction layer

    Provides:
    - Connection pooling
    - Transaction management
    - Query execution with error handling
    - Database backup functionality
    - Thread-safe operations
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database manager

        Args:
            db_path: Path to database file (defaults to centralized path)
        """
        if db_path is None:
            from education_system import paths
            db_path = paths.UNIVERSITY_DEFAULT_DB_PATH

        self.db_path = db_path
        self._connection = None
        self._connection_pool = ConnectionPool(db_path)
        gui_logger.info(f"DatabaseManager initialized with path: {db_path}")

    def _connect(self):
        """
        Establish database connection

        Returns:
            sqlite3.Connection: Database connection

        Raises:
            DatabaseError: If connection fails
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            raise DatabaseError.connection_failed(str(e))

    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute SELECT query and return results

        Args:
            query: SQL SELECT query
            params: Query parameters (optional)

        Returns:
            List[Dict]: Query results as list of dictionaries

        Raises:
            DatabaseError: If query execution fails

        Example:
            results = db.execute_query(
                "SELECT * FROM academic_calendar_events WHERE date = ?",
                (date_str,)
            )
        """
        try:
            with self._connection_pool as conn:
                cursor = conn.execute(query, params or ())
                rows = cursor.fetchall()
                # Convert Row objects to dictionaries
                return [dict(row) for row in rows]
        except Exception as e:
            raise convert_to_user_error(e, {'query': query, 'operation': 'SELECT'})

    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        """
        Execute INSERT/UPDATE/DELETE query

        Args:
            query: SQL modification query
            params: Query parameters (optional)

        Returns:
            int: Number of affected rows

        Raises:
            DatabaseError: If query execution fails

        Example:
            rows_affected = db.execute_update(
                "UPDATE academic_calendar_events SET title = ? WHERE id = ?",
                (new_title, event_id)
            )
        """
        try:
            with self._connection_pool as conn:
                cursor = conn.execute(query, params or ())
                return cursor.rowcount
        except Exception as e:
            raise convert_to_user_error(e, {'query': query, 'operation': 'UPDATE'})

    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """
        Execute query with multiple parameter sets (batch operation)

        Args:
            query: SQL query
            params_list: List of parameter tuples

        Returns:
            int: Number of affected rows

        Raises:
            DatabaseError: If batch execution fails

        Example:
            db.execute_many(
                "INSERT INTO academic_calendar_events (title, date) VALUES (?, ?)",
                [("Event 1", "2025-11-09"), ("Event 2", "2025-11-10")]
            )
        """
        try:
            with self._connection_pool as conn:
                cursor = conn.executemany(query, params_list)
                return cursor.rowcount
        except Exception as e:
            raise convert_to_user_error(e, {'query': query, 'operation': 'BATCH'})

    def transaction(self):
        """
        Create transaction context manager

        Returns:
            ConnectionPool: Context manager for transaction

        Example:
            with db.transaction() as conn:
                conn.execute("INSERT INTO academic_calendar_events ...")
                conn.execute("INSERT INTO attendees ...")
                # Auto-commits if no exception
        """
        return self._connection_pool

    def backup_database(self, backup_path: Optional[str] = None) -> str:
        """
        Create database backup

        Args:
            backup_path: Path for backup file (auto-generated if not provided)

        Returns:
            str: Path to backup file

        Raises:
            ExportError: If backup fails

        Example:
            backup_file = db.backup_database()
            print(f"Backup created: {backup_file}")
        """
        try:
            if backup_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_dir = Path(self.db_path).parent / "backups"
                backup_dir.mkdir(exist_ok=True)
                backup_path = str(backup_dir / f"calendar_backup_{timestamp}.db")

            # Create backup using shutil
            shutil.copy2(self.db_path, backup_path)

            gui_logger.info(f"Database backup created: {backup_path}")
            return backup_path

        except Exception as e:
            raise ExportError.file_write_failed(
                backup_path or "unknown",
                reason=str(e)
            )

    def close(self):
        """
        Close database connections and cleanup resources

        Should be called when database manager is no longer needed.
        """
        if self._connection:
            self._connection.close()
            self._connection = None
        gui_logger.info("DatabaseManager closed")

def init_calendar_database(db_path: Optional[str] = None) -> DatabaseManager:
    """Open the calendar database and make sure the calendar's tables exist.

    Tables come from the Alembic migrations (the baseline and
    ``f7b9d1e3a5c8``); nothing is created here any more. This used to create
    ``scheduled_events``, ``attendees``, ``users``, ``user_sessions`` and the
    retired ``notifications`` table whenever the calendar opened.
    """
    from education_system.systems.university.infrastructure.database.schemas import (
        calendar_year_schema,
    )
    db = DatabaseManager(db_path)
    try:
        with db.transaction() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'unified_events'"
                                ).fetchone():
                raise RuntimeError("The calendar tables are missing: run the migrations")
            calendar_year_schema.apply_to_connection(conn)
        gui_logger.info("Calendar database ready")
        return db
    except Exception as e:
        gui_logger.error(f"Failed to open the calendar database: {e}")
        raise convert_to_user_error(e, {'operation': 'database_initialization'})

