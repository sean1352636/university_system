from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
from education_system.systems.university.infrastructure.logging.log_config import configure_logging
from contextlib import contextmanager

from education_system.systems.university.domain.academics.services.plagiarism.exceptions import DatabaseError

logger = configure_logging(name=__name__)


@contextmanager
def get_safe_db_connection(db_path=str(DEFAULT_DB_PATH)):
    """Safe database connection context manager"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.execute('PRAGMA foreign_keys = ON')
        yield conn
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise DatabaseError(f"Database operation failed: {e}")
    except (ValueError, TypeError, KeyError):
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Unexpected database error: {e}")
        raise DatabaseError(f"Unexpected database error: {e}")
    finally:
        if conn:
            conn.close()
