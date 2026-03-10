from . import _common
from ._common import sqlite3, get_text, logging, time, traceback, DEFAULT_DB_PATH, datetime


def get_db_connection(timeout=30.0, max_retries=3):
    """Get a database connection with proper timeout and retry logic.

    Uses the centralized get_connection() function which maintains thread safety
    by keeping check_same_thread=True (SQLite default). Each thread gets its own
    connection to prevent cross-thread data corruption.
    """
    from education_system.university_system.infrastructure.database.db import get_connection

    retry_delay = 0.1

    for attempt in range(max_retries):
        try:
            # Use centralized get_connection which is thread-safe
            # check_same_thread=True is maintained (the safe default)
            conn = get_connection(db_path=DEFAULT_DB_PATH, timeout=timeout)

            # Additional PRAGMA settings for this module's needs
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA mmap_size = 268435456")  # 256MB
            conn.execute("PRAGMA cache_size = 10000")
            return conn

        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logging.warning(get_text("mobility.trip_management.database.locked_retrying", "Database locked, retrying... (attempt {attempt})").format(attempt=attempt + 1))
                time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                continue
            else:
                logging.error(get_text("mobility.trip_management.database.connection_error_attempts", "Database connection error after {attempts} attempts: {error}").format(attempts=attempt + 1, error=e))
                return None
        except sqlite3.Error as e:
            logging.error(get_text("mobility.trip_management.database.connection_error", "Database connection error: {error}").format(error=e))
            return None

def safe_db_operation(operation_func, *args, max_retries=3, **kwargs):
    """Safely execute a database operation with retry logic"""
    retry_delay = 0.1
    last_error = None

    for attempt in range(max_retries):
        conn = None
        try:
            conn = get_db_connection(timeout=30.0)
            if not conn:
                last_error = get_text("mobility.trip_management.database.failed_establish", "Failed to establish database connection")
                if attempt < max_retries - 1:
                    logging.warning(get_text("mobility.trip_management.database.connection_failed_retrying", "Database connection failed, retrying... (attempt {attempt})").format(attempt=attempt + 1))
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                logging.error(get_text("mobility.trip_management.database.connection_failed_attempts", "Database connection failed after {max_retries} attempts").format(max_retries=max_retries))
                return False

            result = operation_func(conn, *args, **kwargs)
            conn.commit()
            return result

        except sqlite3.OperationalError as e:
            last_error = e
            if conn:
                try:
                    conn.rollback()
                    logging.debug(f"Successfully rolled back transaction after operational error")
                except sqlite3.Error as rollback_error:
                    logging.warning(f"Failed to rollback transaction after operational error: {rollback_error}")
                except Exception as rollback_error:
                    logging.error(f"Unexpected error during rollback after operational error: {type(rollback_error).__name__}: {rollback_error}")

            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logging.warning(get_text("mobility.trip_management.database.locked_retrying_wait", "Database locked, retrying in {wait_time}s... (attempt {attempt})").format(wait_time=f"{wait_time:.2f}", attempt=attempt + 1))
                time.sleep(wait_time)
                continue
            else:
                logging.error(get_text("mobility.trip_management.database.operational_error", "Database operational error: {error}").format(error=e))
                return False

        except sqlite3.Error as e:
            last_error = e
            if conn:
                try:
                    conn.rollback()
                    logging.debug(f"Successfully rolled back transaction after database error")
                except sqlite3.Error as rollback_error:
                    logging.warning(f"Failed to rollback transaction after database error: {rollback_error}")
                except Exception as rollback_error:
                    logging.error(f"Unexpected error during rollback after database error: {type(rollback_error).__name__}: {rollback_error}")
            logging.error(get_text("mobility.trip_management.database.error", "Database error: {error}").format(error=e))
            return False

        except Exception as e:
            last_error = e
            if conn:
                try:
                    conn.rollback()
                    logging.debug(get_text("mobility.trip_management.database.rollback_success_unexpected", "Successfully rolled back transaction after unexpected error"))
                except sqlite3.Error as rollback_error:
                    logging.warning(get_text("mobility.trip_management.database.rollback_failed_unexpected", "Failed to rollback transaction after unexpected error: {error}").format(error=rollback_error))
                except Exception as rollback_error:
                    logging.error(get_text("mobility.trip_management.database.multiple_errors_rollback", "Critical: Multiple errors during rollback - original: {orig_type}: {orig_error}, rollback: {rb_type}: {rb_error}").format(orig_type=type(e).__name__, orig_error=e, rb_type=type(rollback_error).__name__, rb_error=rollback_error))
            logging.error(get_text("mobility.trip_management.errors.unexpected", "Unexpected error: {error_type}: {error}").format(error_type=type(e).__name__, error=e))
            logging.debug(f"Unexpected error traceback: {traceback.format_exc()}")
            return False

        finally:
            if conn:
                try:
                    conn.close()
                    logging.debug(f"Database connection closed successfully")
                except sqlite3.Error as close_error:
                    logging.warning(f"SQLite error closing database connection: {close_error}")
                except Exception as close_error:
                    logging.error(f"Unexpected error closing database connection: {type(close_error).__name__}: {close_error}")

    logging.error(get_text("mobility.trip_management.database.operation_failed_attempts", "Operation failed after {max_retries} attempts. Last error: {error_type}: {error}").format(max_retries=max_retries, error_type=type(last_error).__name__, error=last_error))
    return False

def init_trip_db():
    """Initialize trip management database tables"""
    def create_tables(conn):
        cursor = conn.cursor()

        try:
            # Create trips table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_name TEXT NOT NULL,
                description TEXT,
                destination TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                max_participants INTEGER DEFAULT 50,
                cost REAL DEFAULT 0.0,
                status TEXT DEFAULT 'planning',
                created_by INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (created_by) REFERENCES users (id),
                CHECK (status IN ('planning', 'open', 'full', 'cancelled', 'completed'))
            )
            ''')

            # Create trip_participants table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trip_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                student_id TEXT,
                user_id INTEGER,
                registration_date TEXT NOT NULL,
                payment_status TEXT DEFAULT 'pending',
                emergency_contact TEXT,
                medical_info TEXT,
                dietary_requirements TEXT,
                status TEXT DEFAULT 'registered',
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE (trip_id, student_id),
                CHECK (payment_status IN ('pending', 'partial', 'paid', 'refunded')),
                CHECK (status IN ('registered', 'waitlist', 'cancelled', 'attended'))
            )
            ''')

            # Create trip_staff table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trip_staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                staff_user_id INTEGER NOT NULL,
                role TEXT DEFAULT 'supervisor',
                assigned_date TEXT NOT NULL,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                FOREIGN KEY (staff_user_id) REFERENCES users (id),
                UNIQUE (trip_id, staff_user_id),
                CHECK (role IN ('supervisor', 'coordinator', 'medical', 'transport'))
            )
            ''')

            # Create trip_expenses table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trip_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                date TEXT NOT NULL,
                recorded_by INTEGER,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                FOREIGN KEY (recorded_by) REFERENCES users (id)
            )
            ''')

            # Create trip_itinerary table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trip_itinerary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                activity TEXT NOT NULL,
                location TEXT,
                start_time TEXT,
                end_time TEXT,
                notes TEXT,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                UNIQUE (trip_id, day_number, start_time)
            )
            ''')

            logging.info(get_text("mobility.trip_management.database.tables_created", "Trip management tables created successfully"))
            return True

        except sqlite3.Error as e:
            logging.error(get_text("mobility.trip_management.database.error_creating_tables", "Error creating trip tables: {error}").format(error=e))
            raise e

    return safe_db_operation(create_tables)
