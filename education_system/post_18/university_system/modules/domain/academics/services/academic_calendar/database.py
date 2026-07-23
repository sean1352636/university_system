from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import uuid
import threading
import logging
from typing import List, Tuple
from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
from education_system.post_18.university_system.core.sql_safety import validate_identifier  # nosec B608
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.exceptions import DatabaseError

logger = configure_logging(name=__name__)

# Database connection manager
class DatabaseManager:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.conn = None
        self.cursor = None
        self._lock = threading.RLock()
        self._in_transaction = False  # Track if we're inside a transaction
        self._connect()

    def _connect(self):
        """Establish database connection with proper configuration.

        Uses thread-local storage pattern for thread safety. Each thread that
        calls this will get its own connection with check_same_thread=True
        (the safe default), preventing cross-thread data corruption.

        Note: This class uses a lock (_lock) for synchronizing operations,
        but each thread still maintains its own connection for SQLite safety.
        """
        import threading

        try:
            # Create connection with thread safety enabled (default)
            # check_same_thread=True ensures SQLite's thread safety model is respected
            self.conn = sqlite3.connect(
                self.db_file,
                check_same_thread=True,  # SECURITY: Keep thread safety enabled
                timeout=30.0,
                isolation_level='DEFERRED'  # Use DEFERRED for proper transaction support
            )
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()

            # Configure SQLite for better performance and security
            # Note: foreign_keys, journal_mode=WAL, synchronous=NORMAL, and
            # busy_timeout are already applied by the central database proxy
            # (infrastructure/database/db.py) when sqlite3.connect() is called.
            pragma_commands = [
                "PRAGMA cache_size = 10000",
                "PRAGMA temp_store = MEMORY"
            ]

            for pragma in pragma_commands:
                self.cursor.execute(pragma)

            logger.debug(f"Database connection established for thread {threading.get_ident()}")

        except sqlite3.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise DatabaseError(f"Failed to connect to database: {e}")

    def execute_query(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Execute a SELECT query safely with connection pooling"""
        with self._lock:
            try:
                self.cursor.execute(query, params)
                return self.cursor.fetchall()
            except sqlite3.Error as e:
                # Enhanced error logging with query details
                logger.error(f"Query execution failed: {e}")
                logger.error(f"Failed query: {query[:500]}")  # Log first 500 chars of query
                logger.error(f"Query params: {params}")
                raise DatabaseError(f"Query failed: {e}")

    def execute_update(self, query: str, params: Tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE/DDL query safely"""
        with self._lock:
            try:
                self.cursor.execute(query, params)
                # Only commit if not inside a transaction (savepoint handles commit)
                if not self._in_transaction:
                    self.conn.commit()
                return self.cursor.rowcount
            except sqlite3.Error as e:
                logger.error(f"Update execution failed: {e}")
                raise DatabaseError(f"Update failed: {e}")

    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """Execute many operations efficiently"""
        with self._lock:
            try:
                self.cursor.executemany(query, params_list)
                return self.cursor.rowcount
            except sqlite3.Error as e:
                logger.error(f"Batch execution failed: {e}")
                raise DatabaseError(f"Batch operation failed: {e}")

    def transaction(self):
        """Context manager for database transactions"""
        return DatabaseTransaction(self)

    def backup_database(self, backup_path: str):
        """Create database backup"""
        with self._lock:
            try:
                backup = sqlite3.connect(backup_path)
                self.conn.backup(backup)
                backup.close()
                logger.info(f"Database backed up to {backup_path}")
            except sqlite3.Error as e:
                logger.error(f"Backup failed: {e}")
                raise DatabaseError(f"Backup failed: {e}")

    def close(self):
        """Close database connection"""
        with self._lock:
            if self.conn:
                self.conn.close()
                self.conn = None
                self.cursor = None

class DatabaseTransaction:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.connection = db_manager.conn
        self.lock = db_manager._lock
        self.savepoint = None

    def __enter__(self):
        self.lock.acquire()
        try:
            # Mark that we're inside a transaction (prevents auto-commit in execute_update)
            self.db_manager._in_transaction = True
            # Use savepoints for nested transactions
            self.savepoint = f"sp_{uuid.uuid4().hex[:8]}"
            validate_identifier(self.savepoint, "savepoint")
            self.connection.execute(f"SAVEPOINT {self.savepoint}")
            return self
        except Exception:
            self.db_manager._in_transaction = False
            self.lock.release()
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            validate_identifier(self.savepoint, "savepoint")
            if exc_type is None:
                # Release savepoint and commit the transaction
                self.connection.execute(f"RELEASE SAVEPOINT {self.savepoint}")
                self.connection.commit()
            else:
                self.connection.execute(f"ROLLBACK TO SAVEPOINT {self.savepoint}")
                logger.error(f"Transaction rolled back due to: {exc_val}")
        finally:
            self.db_manager._in_transaction = False
            self.lock.release()
