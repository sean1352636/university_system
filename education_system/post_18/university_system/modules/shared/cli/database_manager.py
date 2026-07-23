"""
Database management for CLI system.

Handles database initialization, schema fixes, migrations, and connection management.
"""

from typing import Optional, Callable, Any

from education_system.post_18.university_system.modules.shared.cli.imports import (
    logging, sqlite3, datetime, time, DB_PATH, logger, _t,
    log_activity, validate_table_name, validate_column_definition,
    safe_alter_table_add_column, SQLIdentifierError, get_auth, set_auth,
    UserAuth, paths, get_global_auth, set_global_auth, set_auth_instance, defaults,
    compulsory_module_1, compulsory_module_2,
    optional_module_1, optional_module_2, optional_module_3, optional_module_4,
    CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
    DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4,
    # Student Union modules
    su_club, su_event, su_fac, su_admin, su_elec, su_fin, student_union_core,
    # Academic calendar
    ensure_calendar_permissions, set_calendar_auth,
    # Assignment system
    init_assignment_system, add_assignment_permissions,
    # Parent portal
    integrate_parent_portal_with_main,
    # Housing
    init_housing_db, set_accommodation_auth,
    # Shop management
    init_shop_db, setup_shop_permissions, set_shop_auth,
    # Trip management
    init_trip_db, setup_trip_permissions, set_trip_auth,
    # Charity shop
    init_charity_shop_db, setup_charity_shop_permissions, set_charity_shop_auth,
    # Cafe
    init_cafe_db, setup_cafe_permissions, set_cafe_auth,
    # Takeaway
    init_takeaway_db, setup_takeaway_permissions, set_takeaway_auth,
    # Grocery
    init_grocery_db, setup_grocery_permissions, set_grocery_auth,
    # Staff HR
    init_staff_hr_db, setup_staff_hr_permissions, set_staff_hr_auth,
    # MFA
    MFA_INTEGRATION_AVAILABLE,
)

# Import exception types
from education_system.post_18.university_system.core.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
)

# Import from auth_manager (avoid circular import by doing it here)
from education_system.post_18.university_system.modules.shared.cli import auth_manager

# Import from integration_manager
from education_system.post_18.university_system.modules.shared.cli.integration_manager import ensure_communication_integration_on_startup

# Import from chatbot_integration
from education_system.post_18.university_system.modules.shared.cli.chatbot_integration import initialize_chatbot_integration, setup_chatbot_permissions

# Import from ai_tools_integration
from education_system.post_18.university_system.modules.shared.cli.ai_tools_integration import integrate_ai_detector_with_main

# Global auth instance
auth = None

# Import missing database initialization functions
try:
    from education_system.post_18.university_system.modules.domain.academics.services.library.database import init_library_db
except ImportError:
    init_library_db = lambda: False

try:
    from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import init_parking_db
except ImportError:
    init_parking_db = lambda: False

try:
    from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management import init_alumni_db
except ImportError:
    init_alumni_db = lambda: False

try:
    from education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management import init_restaurant_db
except ImportError:
    init_restaurant_db = lambda: False

try:
    from education_system.post_18.university_system.modules.domain.student_affairs.services.career_services.internship import init_internship_db
except ImportError:
    init_internship_db = lambda: False

try:
    from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk import init_helpdesk_db
except ImportError:
    init_helpdesk_db = lambda: False

try:
    from education_system.post_18.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
except ImportError:
    init_student_union_db = lambda: False

try:
    from education_system.post_18.university_system.modules.domain.finance.core.financial_core import initialize_finance
except ImportError:
    initialize_finance = lambda: False

# Import missing auth setter functions
try:
    from education_system.post_18.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import set_auth as set_student_union_auth
except ImportError:
    set_student_union_auth = lambda x: None

try:
    from education_system.post_18.university_system.modules.domain.finance.core.financial_core import set_auth as set_finance_auth
except ImportError:
    set_finance_auth = lambda x: None

try:
    from education_system.post_18.university_system.modules.domain.student_affairs.services.career_services.internship import set_auth as set_internship_auth
except ImportError:
    set_internship_auth = lambda x: None

try:
    from education_system.post_18.university_system.infrastructure.email.admin import set_communication_auth
except ImportError:
    set_communication_auth = lambda x: None

try:
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support import set_auth as set_student_support_auth
except ImportError:
    set_student_support_auth = lambda x: None

try:
    from education_system.post_18.university_system.modules.domain.health.services.medical_accommodation import set_auth as set_medical_accommodation_auth
except ImportError:
    set_medical_accommodation_auth = lambda x: None

try:
    from education_system.post_18.university_system.infrastructure.email.admin import integrate_communication_dashboard_with_main
except ImportError:
    integrate_communication_dashboard_with_main = lambda: None

# Error types
class DatabaseError(Exception):
    pass

class ConfigurationError(Exception):
    pass

class ValidationError(Exception):
    pass


def get_db_connection(
    timeout: float = 30.0, max_retries: int = 3
) -> Optional[sqlite3.Connection]:
    """Get a database connection using centralized connection pool.

    This function delegates to the centralized database module for consistent
    connection management with proper pooling, WAL mode, and PRAGMA settings.

    Args:
        timeout: Database lock timeout in seconds (default: 30.0)
        max_retries: Maximum retry attempts for locked database (default: 3)

    Returns:
        sqlite3.Connection or None if connection fails
    """
    from education_system.post_18.university_system.infrastructure.database.db import get_connection

    retry_delay = 0.1

    for attempt in range(max_retries):
        try:
            # Use centralized connection function which handles PRAGMA settings
            conn = get_connection(db_path=DB_PATH, row_factory=True, timeout=timeout)
            return conn

        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logging.warning(f"Database locked, retrying... (attempt {attempt + 1})")
                time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                continue
            else:
                logging.error(f"Database connection error after {attempt + 1} attempts: {e}")
                return None
        except sqlite3.Error as e:
            logging.error(f"Database connection error: {e}")
            return None


def safe_db_operation_with_retry(
    operation_func: Callable[..., Any], *args: Any, max_retries: int = 3, **kwargs: Any
) -> Any:
    """
    Safely execute a database operation with retry logic and comprehensive error handling.

    Args:
        operation_func: The database operation function to execute
        *args: Arguments to pass to the operation function
        max_retries: Maximum number of retry attempts (default: 3)
        **kwargs: Keyword arguments to pass to the operation function

    Returns:
        Result of the operation function, or False if all attempts failed
    """
    retry_delay = 0.1
    last_error = None

    for attempt in range(max_retries):
        conn = None
        try:
            # Attempt to get database connection
            conn = get_db_connection(timeout=30.0)
            if not conn:
                last_error = "Failed to establish database connection"
                if attempt < max_retries - 1:
                    logging.warning(f"Database connection failed, retrying in {retry_delay * (2 ** attempt):.2f}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                logging.error(f"Database connection failed after {max_retries} attempts")
                return False

            # Execute the database operation
            result = operation_func(conn, *args, **kwargs)

            # Commit the transaction
            conn.commit()

            # Log successful operation if there were previous failures
            if attempt > 0:
                logging.info(f"Database operation succeeded on attempt {attempt + 1}")

            return result

        except sqlite3.OperationalError as e:
            last_error = e

            # Handle rollback for operational errors
            if conn:
                try:
                    conn.rollback()
                    logging.debug("Transaction rolled back successfully")
                except sqlite3.Error as rollback_error:
                    logging.warning(f"Failed to rollback transaction: {rollback_error}")
                except (sqlite3.Error, DatabaseError) as rollback_error:
                    logging.error(f"Unexpected error during rollback: {rollback_error}")

            # Check if this is a database lock error that we can retry
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logging.warning(f"Database locked, retrying in {wait_time:.2f}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                logging.error(f"Database operational error after {attempt + 1} attempts: {e}")
                if attempt >= max_retries - 1:
                    logging.error(f"Database operation failed permanently after {max_retries} attempts")
                    return False

        except sqlite3.IntegrityError as e:
            last_error = e

            # Handle rollback for integrity errors
            if conn:
                try:
                    conn.rollback()
                    logging.debug("Transaction rolled back due to integrity constraint")
                except sqlite3.Error as rollback_error:
                    logging.warning(f"Failed to rollback transaction after integrity error: {rollback_error}")
                except (RuntimeError, OSError) as rollback_error:
                    logging.error(f"Unexpected error during integrity error rollback: {rollback_error}")

            # Integrity errors usually shouldn't be retried as they indicate data conflicts
            logging.error(f"Database integrity error (attempt {attempt + 1}): {e}")
            return False

        except sqlite3.Error as e:
            last_error = e

            # Handle rollback for other SQLite errors
            if conn:
                try:
                    conn.rollback()
                    logging.debug("Transaction rolled back due to SQLite error")
                except sqlite3.Error as rollback_error:
                    logging.warning(f"Failed to rollback transaction after SQLite error: {rollback_error}")
                except (RuntimeError, OSError) as rollback_error:
                    logging.error(f"Unexpected error during SQLite error rollback: {rollback_error}")

            logging.error(f"SQLite error (attempt {attempt + 1}): {e}")

            # Retry for certain types of SQLite errors
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logging.info(f"Retrying database operation in {wait_time:.2f}s...")
                time.sleep(wait_time)
                continue
            return False

        except (DatabaseError, ValueError, TypeError) as e:
            last_error = e

            # Handle rollback for unexpected errors
            if conn:
                try:
                    conn.rollback()
                    logging.debug("Transaction rolled back due to unexpected error")
                except sqlite3.Error as rollback_error:
                    logging.warning(f"Failed to rollback transaction after unexpected error: {rollback_error}")
                except (RuntimeError, OSError) as rollback_error:
                    logging.error(f"Critical: Multiple errors during rollback - original: {e}, rollback: {rollback_error}")

            logging.error(f"Unexpected error in database operation (attempt {attempt + 1}): {e}")

            # Retry for unexpected errors, but with caution
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logging.info(f"Retrying after unexpected error in {wait_time:.2f}s...")
                time.sleep(wait_time)
                continue
            return False

        finally:
            # Ensure connection is properly closed
            if conn:
                try:
                    conn.close()
                    logging.debug("Database connection closed successfully")
                except sqlite3.Error as close_error:
                    logging.warning(f"Error closing database connection: {close_error}")
                except (RuntimeError, OSError) as close_error:
                    logging.error(f"Unexpected error while closing database connection: {close_error}")
                    # Don't re-raise here as we want to preserve the original error

    # If we've exhausted all retries
    if last_error:
        logging.error(f"Database operation failed permanently after {max_retries} attempts. Last error: {last_error}")
    else:
        logging.error(f"Database operation failed permanently after {max_retries} attempts due to unknown error")

    return False

# Add this function to fix the missing parent_user_mapping table


def enhanced_db_operation(operation_func, *args, **kwargs):
    """
    Enhanced wrapper for database operations with better error categorization.

    Args:
        operation_func: The database operation function to execute
        *args: Arguments to pass to the operation function
        **kwargs: Keyword arguments to pass to the operation function

    Returns:
        Tuple of (success: bool, result: any, error_type: str)
    """
    try:
        result = safe_db_operation_with_retry(operation_func, *args, **kwargs)

        if result is False:
            return False, None, "operation_failed"

        return True, result, None

    except sqlite3.IntegrityError as e:
        logging.error(f"Data integrity violation: {e}")
        return False, None, "integrity_error"

    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower():
            logging.error(f"Database access conflict: {e}")
            return False, None, "database_locked"
        else:
            logging.error(f"Database operational issue: {e}")
            return False, None, "operational_error"

    except (sqlite3.Error, DatabaseError, ValueError, TypeError) as e:
        logging.error(f"Unexpected error in database operation: {e}")
        return False, None, "unexpected_error"


# Example usage function that demonstrates the improved error handling


def handle_database_error(operation_name, error):
    """Centralized database error handling"""
    logging.error(f"{operation_name} failed: {error}")
    if "UNIQUE constraint failed" in str(error):
        return "duplicate_entry"
    elif "database is locked" in str(error):
        return "database_locked"
    else:
        return "general_error"


def fix_accommodation_schema():
    """Fix accommodation database schema during startup"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Fix audit_log table - check if it exists first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
        if not cursor.fetchone():
            # Create audit_log table if it doesn't exist
            cursor.execute('''
                CREATE TABLE audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    accommodation_id INTEGER,
                    details TEXT,
                    ip_address TEXT,
                    timestamp TEXT NOT NULL
                )
            ''')
            logger.info("Created audit_log table with all required columns")
        else:
            # Table exists, add missing columns
            cursor.execute("PRAGMA table_info(audit_log)")
            columns = [row[1] for row in cursor.fetchall()]

            missing_columns = {
                'accommodation_id': 'INTEGER',
                'details': 'TEXT',
                'ip_address': 'TEXT'
            }

            for col_name, col_type in missing_columns.items():
                if col_name not in columns:
                    try:
                        # Validate column definition using SQL safety module
                        col_def = validate_column_definition(col_name, col_type)
                        cursor.execute(f'ALTER TABLE audit_log ADD COLUMN [{col_def.name}] {col_def.type_def}')
                        logger.info(f"Added column '{col_name}' to audit_log table")
                    except SQLIdentifierError as e:
                        logger.warning(f"Invalid column definition for '{col_name}': {e}")
                        continue

        # Also ensure accommodations table has all required columns
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accommodations'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(accommodations)")
            acc_columns = [row[1] for row in cursor.fetchall()]

            required_acc_columns = {
                'status': 'TEXT DEFAULT "active"',
                'approved_by': 'TEXT',
                'approval_date': 'TEXT',
                'notes': 'TEXT'
            }

            for col_name, col_type in required_acc_columns.items():
                if col_name not in acc_columns:
                    try:
                        # Validate column definition using SQL safety module
                        col_def = validate_column_definition(col_name, col_type)
                        cursor.execute(f'ALTER TABLE accommodations ADD COLUMN [{col_def.name}] {col_def.type_def}')
                        logger.info(f"Added column '{col_name}' to accommodations table")
                    except SQLIdentifierError as e:
                        logger.warning(f"Invalid column definition for '{col_name}': {e}")
                        continue

        conn.commit()
        conn.close()
        return True

    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error fixing accommodation schema: {e}")
        logger.warning(f"Could not fix accommodation schema: {e}")
        return False


def fix_parent_portal_database():
    """Fix missing parent portal database tables"""
    from education_system.post_18.university_system.infrastructure.database.db import get_connection

    try:
        # Use centralized connection for schema corrections
        conn = get_connection(db_path=DB_PATH, row_factory=False, timeout=30)
        cursor = conn.cursor()

        logger.info("Fixing parent portal database schema...")

        # Create parent_user_mapping table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_user_mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            parent_id TEXT UNIQUE,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
        )
        ''')

        # Ensure parent_accounts table exists with all required columns
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id TEXT UNIQUE,
            first_name TEXT,
            last_name TEXT,
            email TEXT UNIQUE,
            phone TEXT,
            address TEXT,
            emergency_contact BOOLEAN DEFAULT 0,
            registration_date TEXT,
            two_factor_enabled BOOLEAN DEFAULT 0,
            two_factor_secret TEXT,
            profile_photo TEXT
        )
        ''')

        # Check if parent_accounts table is missing any columns and add them
        cursor.execute("PRAGMA table_info(parent_accounts)")
        existing_columns = [column[1] for column in cursor.fetchall()]

        required_columns = {
            'two_factor_enabled': 'BOOLEAN DEFAULT 0',
            'two_factor_secret': 'TEXT',
            'profile_photo': 'TEXT'
        }

        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                try:
                    # Validate column definition using SQL safety module
                    col_def = validate_column_definition(column_name, column_type)
                    cursor.execute(f'ALTER TABLE parent_accounts ADD COLUMN [{col_def.name}] {col_def.type_def}')
                    logger.info(f"Added column '{column_name}' to parent_accounts table")
                except SQLIdentifierError as e:
                    logger.warning(f"Invalid column definition for '{column_name}': {e}")
                    continue
                except (sqlite3.Error, DatabaseError) as e:
                    logger.warning(f"Could not add column '{column_name}': {e}")

        # Create parent_student_relationships table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_student_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id TEXT,
            student_id TEXT,
            relationship_type TEXT,
            access_level TEXT DEFAULT 'full',
            date_added TEXT,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Create parent_preferences table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id TEXT UNIQUE,
            email_notifications BOOLEAN DEFAULT 1,
            sms_notifications BOOLEAN DEFAULT 0,
            grade_alerts BOOLEAN DEFAULT 1,
            attendance_alerts BOOLEAN DEFAULT 1,
            behavior_alerts BOOLEAN DEFAULT 1,
            assignment_alerts BOOLEAN DEFAULT 0,
            weekly_summary BOOLEAN DEFAULT 1,
            notification_timing TEXT DEFAULT '08:00',
            quiet_hours_start TEXT DEFAULT '20:00',
            quiet_hours_end TEXT DEFAULT '07:00',
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
        )
        ''')

        # Create other essential parent portal tables
        essential_tables = [
            ('parent_notifications', '''
            CREATE TABLE IF NOT EXISTS parent_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                student_id TEXT,
                notification_type TEXT,
                notification_content TEXT,
                created_date TEXT,
                read_status BOOLEAN DEFAULT 0,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            '''),

            ('parent_messages', '''
            CREATE TABLE IF NOT EXISTS parent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                teacher_id INTEGER,
                student_id TEXT,
                message_content TEXT,
                created_date TEXT,
                is_read BOOLEAN DEFAULT 0,
                is_from_parent BOOLEAN DEFAULT 1,
                message_type TEXT DEFAULT 'individual',
                group_id TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                FOREIGN KEY (teacher_id) REFERENCES users (id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            '''),

            ('parent_activity_log', '''
            CREATE TABLE IF NOT EXISTS parent_activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                action TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            )
            ''')
        ]

        for table_name, create_sql in essential_tables:
            cursor.execute(create_sql)
            logger.info(f"Ensured {table_name} table exists")

        conn.commit()
        conn.close()

        logger.info("Parent portal database schema fix completed successfully!")
        return True

    except (sqlite3.Error, DatabaseError) as e:
        logger.error(f"Error fixing parent portal database schema: {e}")
        return False


def fix_ai_detector_database_schema():
    """Fix AI detector database schema by creating proper tables"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        logger.info("Fixing AI detector database schema...")

        # Create AI detector submissions table with correct column names
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_detector_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            submission_text TEXT NOT NULL,
            title TEXT,
            course_code TEXT,
            assignment_id TEXT,
            submission_date TEXT NOT NULL,
            word_count INTEGER,
            character_count INTEGER,
            institution_id TEXT
        )
        ''')

        # Create AI detector results table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_detector_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            ai_score REAL NOT NULL,
            confidence REAL NOT NULL,
            detailed_results TEXT,
            created_at TEXT NOT NULL,
            style_deviation REAL,
            FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
        )
        ''')

        # Check if we need to migrate old data or add missing columns
        cursor.execute("PRAGMA table_info(ai_detector_submissions)")
        existing_columns = [column[1] for column in cursor.fetchall()]

        # Add missing columns if they don't exist
        required_columns = {
            'title': 'TEXT',
            'course_code': 'TEXT',
            'assignment_id': 'TEXT',
            'word_count': 'INTEGER',
            'character_count': 'INTEGER',
            'institution_id': 'TEXT'
        }

        # Use centralized SQL safety validation for column definitions
        for column_name, column_def in required_columns.items():
            if column_name not in existing_columns:
                try:
                    # Validate column definition using SQL safety module
                    col_def = validate_column_definition(column_name, column_def)
                    cursor.execute(f'ALTER TABLE ai_detector_submissions ADD COLUMN [{col_def.name}] {col_def.type_def}')
                    logger.info(f"Added column '{column_name}' to ai_detector_submissions table")
                except SQLIdentifierError as e:
                    logger.warning(f"Invalid column definition for '{column_name}': {e}")
                    continue
                except (sqlite3.Error, DatabaseError) as e:
                    logger.warning(f"Could not add column '{column_name}': {e}")

        # Check if we have the wrong column name and need to rename
        if 'submission_title' in existing_columns and 'title' not in existing_columns:
            try:
                # SQLite doesn't support RENAME COLUMN directly in older versions
                # So we'll create a new table and copy data
                cursor.execute('''
                CREATE TABLE ai_detector_submissions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    submission_text TEXT NOT NULL,
                    title TEXT,
                    course_code TEXT,
                    assignment_id TEXT,
                    submission_date TEXT NOT NULL,
                    word_count INTEGER,
                    character_count INTEGER,
                    institution_id TEXT
                )
                ''')

                # Copy data from old table to new table
                cursor.execute('''
                INSERT INTO ai_detector_submissions_new
                (id, student_id, submission_text, title, course_code, assignment_id,
                 submission_date, word_count, character_count, institution_id)
                SELECT id, student_id, submission_text, submission_title, course_code, assignment_id,
                       submission_date, word_count, character_count, institution_id
                FROM ai_detector_submissions
                ''')

                # Drop old table and rename new one
                cursor.execute('DROP TABLE ai_detector_submissions')
                cursor.execute('ALTER TABLE ai_detector_submissions_new RENAME TO ai_detector_submissions')

                logger.info("Migrated 'submission_title' column to 'title'")

            except (sqlite3.Error, DatabaseError) as e:
                logger.warning(f"Could not migrate submission_title column: {e}")

        conn.commit()
        conn.close()

        logger.info("AI detector database schema fix completed!")
        return True

    except (sqlite3.Error, DatabaseError) as e:
        logger.error(f"Error fixing AI detector database schema: {e}")
        return False


def fix_support_database_schema():
    """
    Fix the support database schema by adding missing columns.
    Call this function before initializing the EnhancedStudentSupport system.
    """
    from education_system.post_18.university_system.infrastructure.database.db import get_connection

    try:
        conn = get_connection(db_path=DB_PATH, row_factory=False)
        cursor = conn.cursor()

        logger.info("Fixing support database schema...")

        # Check if support_tickets table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='support_tickets'")
        if not cursor.fetchone():
            logger.error("support_tickets table does not exist. Creating it...")
            cursor.execute('''
            CREATE TABLE support_tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                user_id INTEGER,
                subject TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                assigned_to TEXT,
                escalated_at TEXT,
                resolved_at TEXT,
                closed_at TEXT,
                estimated_resolution TEXT,
                sentiment TEXT DEFAULT 'neutral',
                satisfaction_rating INTEGER,
                tags TEXT,
                parent_ticket_id INTEGER,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (parent_ticket_id) REFERENCES support_tickets (ticket_id)
            )
            ''')
            logger.info("Created support_tickets table with all required columns")
        else:
            # Table exists, check and add missing columns
            cursor.execute("PRAGMA table_info(support_tickets)")
            existing_columns = [column[1] for column in cursor.fetchall()]

            # Ensure core columns exist for analytics and SLA tracking
            required_columns = {
                'created_at': 'TEXT',
                'updated_at': 'TEXT',
                'escalated_at': 'TEXT',
                'resolved_at': 'TEXT',
                'closed_at': 'TEXT',
                'estimated_resolution': 'TEXT',
                'sentiment': 'TEXT',
                'satisfaction_rating': 'INTEGER',
                'tags': 'TEXT',
                'parent_ticket_id': 'INTEGER',
                'subject': 'TEXT',
                'description': 'TEXT'
            }

            for column_name, column_type in required_columns.items():
                if column_name not in existing_columns:
                    try:
                        # Validate column definition using SQL safety module
                        col_def = validate_column_definition(column_name, column_type)
                        cursor.execute(f'ALTER TABLE support_tickets ADD COLUMN [{col_def.name}] {col_def.type_def}')
                        logger.info(f"Added column '{column_name}' to support_tickets table")
                    except SQLIdentifierError as e:
                        logger.warning(f"Invalid column definition for '{column_name}': {e}")
                        continue
                    except (sqlite3.Error, DatabaseError) as e:
                        logger.warning(f"Could not add column '{column_name}': {e}")

            if 'user_id' not in existing_columns:
                try:
                    # Validate column definition using SQL safety module
                    col_def = validate_column_definition('user_id', 'INTEGER')
                    cursor.execute(f'ALTER TABLE support_tickets ADD COLUMN [{col_def.name}] {col_def.type_def}')
                    logger.info("Added column 'user_id' to support_tickets table")
                except SQLIdentifierError as e:
                    logger.warning(f"Invalid column definition for 'user_id': {e}")
                except (sqlite3.Error, DatabaseError) as e:
                    logger.warning(f"Could not add column 'user_id': {e}")

        # Fix any existing tickets that have NULL created_at
        cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE created_at IS NULL OR created_at = ''")
        null_datetime_count = cursor.fetchone()[0]

        if null_datetime_count > 0:
            logger.info(f"Fixing {null_datetime_count} tickets with missing created_at...")
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            UPDATE support_tickets
            SET created_at = ?
            WHERE created_at IS NULL OR created_at = ''
            ''', (current_time,))
            logger.info(f"Fixed {null_datetime_count} tickets with missing created_at")

        # Create other required tables
        required_tables = {
            'system_metrics': '''
            CREATE TABLE IF NOT EXISTS system_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                category TEXT NOT NULL,
                recorded_datetime TEXT NOT NULL,
                metadata TEXT
            )
            ''',
            'escalation_rules': '''
            CREATE TABLE IF NOT EXISTS escalation_rules (
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                priority TEXT,
                condition_type TEXT NOT NULL,
                condition_value TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_target TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_by TEXT NOT NULL,
                created_datetime TEXT NOT NULL
            )
            '''
        }

        for table_name, create_sql in required_tables.items():
            cursor.execute(create_sql)
            logger.info(f"Ensured {table_name} table exists")

        conn.commit()
        conn.close()

        logger.info("Support database schema fix completed successfully!")
        return True

    except (sqlite3.Error, DatabaseError) as e:
        logger.error(f"Error fixing support database schema: {e}")
        return False


def fix_duplicate_emails():
    """
    Fix duplicate email issues in the users table by making them unique
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Find duplicate emails
        cursor.execute('''
        SELECT email, COUNT(*) as count
        FROM users
        GROUP BY email
        HAVING count > 1
        ''')

        duplicates = cursor.fetchall()

        if not duplicates:
            logger.info("No duplicate emails found.")
            conn.close()
            return True

        logger.info(f"Found {len(duplicates)} duplicate email(s). Fixing...")

        for email, count in duplicates:
            logger.info(f"Fixing duplicate email: {email} (found {count} times)")

            # Get all users with this email
            cursor.execute('''
            SELECT id, username, email
            FROM users
            WHERE email = ?
            ORDER BY id
            ''', (email,))

            users_with_email = cursor.fetchall()

            # Keep the first user with the original email, modify others
            for i, (user_id, username, user_email) in enumerate(users_with_email):
                if i == 0:
                    logger.info(f"Keeping original email for user {username}")
                    continue

                # Generate unique email for subsequent users
                base_email = email.split('@')[0]
                domain = email.split('@')[1]
                new_email = f"{base_email}_{username}@{domain}"

                # Make sure this new email is also unique
                counter = 1
                while True:
                    cursor.execute('SELECT id FROM users WHERE email = ?', (new_email,))
                    if not cursor.fetchone():
                        break
                    new_email = f"{base_email}_{username}_{counter}@{domain}"
                    counter += 1

                # Update the user's email
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                UPDATE users
                SET email = ?, updated_at = ?
                WHERE id = ?
                ''', (new_email, current_time, user_id))

                logger.info(f"Updated user {username} email to: {new_email}")

        conn.commit()
        conn.close()
        logger.info("Duplicate email fix completed successfully!")
        return True

    except sqlite3.Error as e:
        logging.error(f"Database error while fixing duplicate emails: {e}")
        return False
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Unexpected error while fixing duplicate emails: {e}")
        return False


def silent_integrity_check():
    """Perform integrity checks silently during startup"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Check if users table exists first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            # Users table doesn't exist yet, skip integrity check
            conn.close()
            return True

        # Check for and fix duplicate emails silently
        cursor.execute('''
        SELECT email, COUNT(*) as count
        FROM users
        GROUP BY email
        HAVING count > 1
        ''')
        duplicate_emails = cursor.fetchall()

        if duplicate_emails:
            conn.close()
            fix_duplicate_emails()
            return silent_integrity_check()  # Re-check after fix

        # Check for and fix orphaned users silently
        cursor.execute('''
        SELECT u.id, u.username
        FROM users u
        LEFT JOIN user_accounts ua ON u.id = ua.user_id
        WHERE ua.user_id IS NULL
        ''')
        orphaned_users = cursor.fetchall()

        if orphaned_users:
            conn.close()
            # Only try to fix if we have an auth context
            try:
                temp_auth = get_auth()
                if temp_auth and hasattr(temp_auth, 'current_user') and temp_auth.current_user:
                    temp_auth.fix_database_consistency()
                # If no auth context, just log and continue - will be fixed later
            except (sqlite3.Error, DatabaseError) as e:
                logging.debug(f"Could not fix orphaned users during startup: {e}")
            return True

        conn.close()
        return True

    except (sqlite3.Error, DatabaseError) as e:
        logging.debug(f"Silent integrity check info: {e}")  # Changed from warning to debug
        return False


def validate_database_integrity():
    """
    Validate database integrity and fix common issues
    """
    logger.info("Validating database integrity...")

    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        issues_found = []
        fixes_applied = []

        # Check 1: Duplicate emails in users table
        cursor.execute('''
        SELECT email, COUNT(*) as count
        FROM users
        GROUP BY email
        HAVING count > 1
        ''')
        duplicate_emails = cursor.fetchall()

        if duplicate_emails:
            issues_found.append(f"Found {len(duplicate_emails)} duplicate email addresses")

        # Check 2: Duplicate usernames in users table
        cursor.execute('''
        SELECT username, COUNT(*) as count
        FROM users
        GROUP BY username
        HAVING count > 1
        ''')
        duplicate_usernames = cursor.fetchall()

        if duplicate_usernames:
            issues_found.append(f"Found {len(duplicate_usernames)} duplicate usernames")

        # Check 3: Users without corresponding user_accounts
        cursor.execute('''
        SELECT u.id, u.username
        FROM users u
        LEFT JOIN user_accounts ua ON u.id = ua.user_id
        WHERE ua.user_id IS NULL
        ''')
        orphaned_users = cursor.fetchall()

        if orphaned_users:
            issues_found.append(f"Found {len(orphaned_users)} users without accounts")

        # Check 4: User accounts without corresponding users
        cursor.execute('''
        SELECT ua.id, ua.username
        FROM user_accounts ua
        LEFT JOIN users u ON ua.user_id = u.id
        WHERE u.id IS NULL
        ''')
        orphaned_accounts = cursor.fetchall()

        if orphaned_accounts:
            issues_found.append(f"Found {len(orphaned_accounts)} accounts without user profiles")

        conn.close()

        # Report findings
        if issues_found:
            logger.info("Database integrity issues found:")
            for issue in issues_found:
                logger.info(f"{issue}")

            fix_choice = input("\nWould you like to attempt to fix these issues? (y/n): ").lower()
            if fix_choice == 'y':
                # Fix duplicate emails
                if duplicate_emails:
                    if fix_duplicate_emails():
                        fixes_applied.append("Fixed duplicate emails")

                # Fix other issues using existing auth methods
                auth_instance = get_auth()
                if auth_instance and (orphaned_users or orphaned_accounts):
                    if auth_instance.fix_database_consistency():
                        fixes_applied.append("Fixed orphaned users/accounts")

                if fixes_applied:
                    logger.info("Fixes applied:")
                    for fix in fixes_applied:
                        logger.info(f"{fix}")
                    logger.info("Database integrity validation completed!")
                else:
                    logger.info("No fixes could be applied automatically.")
        else:
            logger.info("Database integrity check passed - no issues found!")

        return len(issues_found) == 0

    except (ValueError, TypeError, ValidationError) as e:
        logging.error(f"Error during database integrity validation: {e}")
        return False


def validate_database_integrity_with_admin_context():
    """
    Validate database integrity with admin permissions during startup
    """
    logger.info(_t("cli.system.validating_integrity"))

    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Check if users table exists first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            logger.info(_t("cli.system.users_table_pending"))
            conn.close()
            return True

        issues_found = []
        fixes_applied = []

        # Check 1: Duplicate emails in users table
        cursor.execute('''
        SELECT email, COUNT(*) as count
        FROM users
        GROUP BY email
        HAVING count > 1
        ''')
        duplicate_emails = cursor.fetchall()

        if duplicate_emails:
            issues_found.append(f"Found {len(duplicate_emails)} duplicate email addresses")
            # Auto-fix duplicate emails during startup
            conn.close()
            if fix_duplicate_emails():
                fixes_applied.append("Fixed duplicate emails")
        else:
            conn.close()

        # Check 2: Users without corresponding user_accounts
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            # Check if user_accounts table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_accounts'")
            if cursor.fetchone():
                cursor.execute('''
                SELECT u.id, u.username
                FROM users u
                LEFT JOIN user_accounts ua ON u.id = ua.user_id
                WHERE ua.user_id IS NULL
                ''')
                orphaned_users = cursor.fetchall()

                if orphaned_users:
                    issues_found.append(f"Found {len(orphaned_users)} users without accounts")
                    # We'll let the user authentication system handle this later
                    # to avoid permission issues during startup
                    fixes_applied.append("Marked orphaned users for later fixing")

            conn.close()

        # Report findings
        if issues_found:
            logger.info("Database integrity issues found:")
            for issue in issues_found:
                logger.warning(f"{issue}")
            if fixes_applied:
                logger.info("Fixes applied:")
                for fix in fixes_applied:
                    logger.info(f"{fix}")
        else:
            logger.info("Database integrity check passed - no issues found!")

        return len(issues_found) == 0

    except (AuthenticationError, PermissionDeniedError) as e:
        logging.error(f"Error during database integrity validation: {e}")
        return False


def emergency_fix_database():
    """
    Emergency function to fix database issues
    Call this if you're experiencing UNIQUE constraint errors
    """
    logger.info("Emergency Database Fix Utility")
    logger.info("=" * 40)

    try:
        # Fix duplicate emails
        logger.info("Step 1: Fixing duplicate email addresses...")
        fix_duplicate_emails()

        # Fix orphaned records
        logger.info("Step 2: Fixing orphaned user records...")
        auth_instance = get_auth()
        if auth_instance:
            auth_instance.fix_database_consistency()

        # Validate integrity
        logger.info("Step 3: Final integrity check...")
        validate_database_integrity()

        logger.info("Emergency fix completed!")
        return True

    except (ValueError, TypeError, ValidationError) as e:
        logging.error(f"Emergency fix failed: {e}")
        return False


def cleanup_database_on_startup():
    """Clean up any hanging database connections on startup"""
    try:
        import gc

        # First, try to checkpoint the WAL file - use correct DB path
        conn = get_db_connection(timeout=5.0)
        if conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()

        # Force garbage collection
        gc.collect()

        logger.info("Database cleanup completed successfully.")
        return True
    except (sqlite3.Error, DatabaseError) as e:
        logging.warning(f"Database cleanup warning: {e}")
        return False


def cleanup_database_connections():
    """Function to cleanup database connections - can be called anywhere"""
    cleanup_success = False

    try:
        from education_system.post_18.university_system.infrastructure.database.database_utils import cleanup_database_connections
        cleanup_database_connections()
        cleanup_success = True
        logging.info("Database connections cleaned up successfully")
    except ImportError:
        logging.warning("database_utils module not found, skipping external cleanup")
    except AttributeError:
        logging.warning("cleanup_database_connections function not found in database_utils")
    except (ValueError, TypeError, ValidationError) as e:
        logging.error(f"Error during database cleanup: {e}")

    try:
        # Additional cleanup - force garbage collection
        import gc
        collected = gc.collect()
        logging.debug(f"Garbage collection completed, collected {collected} objects")
        cleanup_success = True
    except ImportError:
        # This should never happen since gc is a built-in module
        logging.error("Failed to import gc module for garbage collection")
    except (RuntimeError, MemoryError) as e:
        logging.error(f"Error during garbage collection: {e}")

    if not cleanup_success:
        logging.warning("Database cleanup completed with some issues")

    return cleanup_success


def init_db():
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # IMPORTANT: Disable foreign keys during initial setup to avoid constraint issues
        cursor.execute("PRAGMA foreign_keys = OFF")

        # Create students table first (no dependencies)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            email_address TEXT,
            title TEXT,
            first_name TEXT,
            middle_name TEXT,
            last_name TEXT,
            gender TEXT,
            dob TEXT,
            age INTEGER,
            course TEXT,
            registration_datetime TEXT,
            status TEXT DEFAULT 'Active',
            enrollment_date TEXT
        )
        ''')

        # Check if students table has the correct number of columns and add missing ones
        cursor.execute("PRAGMA table_info(students)")
        student_columns = [col[1] for col in cursor.fetchall()]

        # Add missing columns if they don't exist
        if 'status' not in student_columns:
            try:
                cursor.execute('ALTER TABLE students ADD COLUMN status TEXT DEFAULT "Active"')
                logger.info("Added status column to students table")
            except (sqlite3.Error, DatabaseError) as e:
                logger.error(f"Error adding status column: {e}")

        if 'enrollment_date' not in student_columns:
            try:
                cursor.execute('ALTER TABLE students ADD COLUMN enrollment_date TEXT')
                logger.info("Added enrollment_date column to students table")
            except (sqlite3.Error, DatabaseError) as e:
                logger.error(f"Error adding enrollment_date column: {e}")

        # Create modules table (no dependencies)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS modules (
            module_code TEXT PRIMARY KEY,
            module_name TEXT,
            module_type TEXT
        )
        ''')

        # Migrate/drop users if old schema detected
        cursor.execute("PRAGMA table_info(users)")
        old_cols = [c[1] for c in cursor.fetchall()]
        if 'username' in old_cols:
            cursor.execute("DROP TABLE IF EXISTS users")

        # Create or alter users table (depends on students)
        cursor.execute("PRAGMA table_info(users)")
        cols = [c[1] for c in cursor.fetchall()]
        if not cols:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                student_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
        else:
            # ensure every new column exists
            required = {
                'first_name': 'TEXT NOT NULL',
                'last_name' : 'TEXT NOT NULL',
                'email'     : 'TEXT UNIQUE NOT NULL',
                'role'      : 'TEXT NOT NULL',
                'student_id': 'TEXT',
                'created_at': 'TEXT NOT NULL',
                'updated_at': 'TEXT NOT NULL'
            }
            # Use centralized SQL safety validation for column definitions
            for col, definition in required.items():
                if col not in cols:
                    try:
                        # Validate column definition using SQL safety module
                        col_def = validate_column_definition(col, definition)
                        cursor.execute(f'ALTER TABLE users ADD COLUMN [{col_def.name}] {col_def.type_def}')
                        logging.info(f"Added column '{col}' to users table")
                    except SQLIdentifierError as e:
                        logging.warning(f"Invalid column definition for '{col}': {e}")
                        continue
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" in str(e).lower():
                            logging.debug(f"Column '{col}' already exists in users table")
                        else:
                            logging.error(f"Failed to add column '{col}' to users table: {e}")
                            # Continue with other columns rather than failing completely
                    except sqlite3.Error as e:
                        logging.error(f"Database error when adding column '{col}': {e}")
                        # Continue with other columns rather than failing completely

        # Create student_grades table (depends on students and modules)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            assessment_name TEXT,
            grade TEXT,
            grade_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Create attendance table (depends on students and modules)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            date TEXT,
            status TEXT,
            reason TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Create student_modules table (depends on students)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_type TEXT,
            module_code TEXT,
            module_name TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # POPULATE MODULES TABLE FIRST (before creating students that reference modules)
        all_modules = [
            (compulsory_module_1['code'], compulsory_module_1['name'], 'compulsory'),
            (compulsory_module_2['code'], compulsory_module_2['name'], 'compulsory'),
            (optional_module_1['code'], optional_module_1['name'], 'optional'),
            (optional_module_2['code'], optional_module_2['name'], 'optional'),
            (optional_module_3['code'], optional_module_3['name'], 'optional'),
            (optional_module_4['code'], optional_module_4['name'], 'optional'),
            (CS_optional_module_1['code'], CS_optional_module_1['name'], 'CS'),
            (CS_optional_module_2['code'], CS_optional_module_2['name'], 'CS'),
            (CS_optional_module_3['code'], CS_optional_module_3['name'], 'CS'),
            (CS_optional_module_4['code'], CS_optional_module_4['name'], 'CS'),
            (DS_optional_module_1['code'], DS_optional_module_1['name'], 'DS'),
            (DS_optional_module_2['code'], DS_optional_module_2['name'], 'DS'),
            (DS_optional_module_3['code'], DS_optional_module_3['name'], 'DS'),
            (DS_optional_module_4['code'], DS_optional_module_4['name'], 'DS')
        ]
        for module_code, module_name, module_type in all_modules:
            cursor.execute('''
            INSERT OR IGNORE INTO modules (module_code, module_name, module_type)
            VALUES (?, ?, ?)
            ''', (module_code, module_name, module_type))

        # ——— PARKING TABLES (these have their own dependencies) ———
        # Create users table dependency first for parking (already created above)

        # Vehicles table (depends on users)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            vehicle_id         TEXT PRIMARY KEY,
            license_plate      TEXT NOT NULL,
            make               TEXT,
            model              TEXT,
            year               INTEGER,
            color              TEXT,
            vehicle_type       TEXT,
            owner_id           INTEGER,
            registration_state TEXT,
            FOREIGN KEY (owner_id) REFERENCES users (id)
        )
        ''')

        # Parking lots table (no dependencies)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_lots (
            lot_id            TEXT PRIMARY KEY,
            lot_name          TEXT,
            location          TEXT,
            total_spaces      INTEGER,
            available_spaces  INTEGER,
            zone              TEXT,
            hours_of_operation TEXT
        )
        ''')

        # Parking spaces table (depends on parking_lots)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_spaces (
            space_id         TEXT PRIMARY KEY,
            lot_id           TEXT,
            space_number     TEXT,
            space_type       TEXT,
            occupancy_status TEXT,
            reserved_for     TEXT,
            FOREIGN KEY (lot_id) REFERENCES parking_lots (lot_id)
        )
        ''')

        # Parking permits table (depends on users and vehicles)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_permits (
            permit_id       TEXT PRIMARY KEY,
            id              INTEGER,
            full_name       TEXT,
            email           TEXT,
            zone            TEXT,
            permit_type     TEXT,
            start_date      TEXT,
            end_date        TEXT,
            active_status   TEXT,
            vehicle_id      TEXT,
            issue_date      TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (vehicle_id),
            FOREIGN KEY (id)         REFERENCES users    (id)
        )
        ''')

        # Violations table (depends on vehicles)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_violations (
            violation_id    TEXT PRIMARY KEY,
            vehicle_id      TEXT,
            license_plate   TEXT,
            violation_type  TEXT,
            violation_date  TEXT,
            fine_amount     REAL,
            payment_status  TEXT,
            location        TEXT,
            officer_id      TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (vehicle_id)
        )
        ''')

        # trip_calendar_events folded into academic_calendar_events
        # (trip_id column links a calendar event to its trip).

        # Commit table creation before inserting data
        conn.commit()

        # CREATE DEFAULT STUDENT RECORD (ONLY ONCE) - Now safe since modules exist
        # Temporarily disable foreign key checks to avoid module_code issues
        cursor.execute("PRAGMA foreign_keys = OFF")

        cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', ('S12345',))
        if cursor.fetchone()[0] == 0:
            now_dt = datetime.now()
            registration_time = now_dt.strftime('%Y-%m-%d %H:%M:%S')
            dob = datetime(2000, 1, 1)
            age = now_dt.year - dob.year - ((now_dt.month, now_dt.day) < (dob.month, dob.day))

            # Create student record
            cursor.execute(
                'INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    'S12345', 'student@example.com', 'Mr', 'Default', 'lucas', 'Student',
                    'male', dob.strftime('%Y-%m-%d'), age, 'CS', registration_time,
                    'Active', registration_time
                )
            )

            # Create student modules - now safe since student exists
            module_data = [
                ('S12345', compulsory_module_1['code']),
                ('S12345', compulsory_module_2['code']),
                ('S12345', optional_module_1['code']),
                ('S12345', optional_module_2['code']),
                ('S12345', CS_optional_module_1['code']),
                ('S12345', CS_optional_module_2['code'])
            ]
            cursor.executemany(
                'INSERT INTO student_modules (student_id, module_code) VALUES (?, ?)',
                module_data
            )

            # Re-enable foreign key checks after student modules insertion
            cursor.execute("PRAGMA foreign_keys = ON")

        # Commit all student data before creating users
        conn.commit()

        # COMMIT ALL CHANGES AND CLOSE
        conn.commit()
        conn.close()

        # CREATE DEFAULT USERS USING CENTRALIZED FUNCTION - Now safe since student exists
        # Call this AFTER closing the connection to avoid lock issues
        auth_manager.ensure_default_users_exist_once()

        logger.info("Database initialized successfully!")
        return True

    except sqlite3.Error as e:
        logging.error(f"An error occurred while initializing the database: {e}")
        # Print more detailed error information
        logger.error(f"Database initialization failed: {e}")
        return False
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Unexpected error during database initialization: {e}")
        logger.error(f"Unexpected error during database initialization: {e}")
        return False


def init_integration_tables():
    """Create tables for system integration - ADD THIS TO main.py"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Create integration tables
        integration_tables = [
            '''CREATE TABLE IF NOT EXISTS attendance_calendar_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attendance_record_id INTEGER,
                event_id TEXT,
                module_code TEXT,
                date TEXT,
                created_at TEXT,
                FOREIGN KEY (attendance_record_id) REFERENCES attendance_records (id),
                FOREIGN KEY (event_id) REFERENCES events (id)
            )''',

            '''CREATE TABLE IF NOT EXISTS system_integration_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_system TEXT,
                target_system TEXT,
                operation TEXT,
                status TEXT,
                details TEXT,
                timestamp TEXT
            )'''
        ]

        for table_sql in integration_tables:
            cursor.execute(table_sql)

        conn.commit()
        conn.close()

        logger.info("Integration tables created successfully!")
        return True

    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error creating integration tables: {e}")
        return False


def init_all_databases():
    """Initialize all required databases"""
    # Use a module-level flag to prevent multiple initializations
    if hasattr(init_all_databases, '_initialization_complete'):
        logger.info("Databases already initialized, skipping...")
        return True

    logger.info("Initializing all databases...")

    # Initialize main database first
    if not init_db():
        logger.error("Failed to initialize main database")
        return False

    # Ensure the health portal schema and security tables are ready before features load
    try:
        logger.info("Initializing health portal schema...")
        from education_system.post_18.university_system.modules.domain.health.portal.health_portal_core import init_enhanced_health_db
        from education_system.post_18.university_system.modules.domain.health.portal.data_privacy import ensure_security_schema

        init_enhanced_health_db()
        ensure_security_schema()
        logger.info("Health portal schema ready")
    except (ValueError, TypeError, ValidationError) as e:
        logging.warning(f"Health portal schema initialization encountered an issue: {e}")

    # Ensure academic calendar core tables exist on the shared database (avoids missing table errors)
    conn = None
    try:
        logger.info("Ensuring academic calendar core tables...")
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS event_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    color_code TEXT,
                    description TEXT,
                    date_added TEXT NOT NULL
                )
            ''')
            conn.commit()
            logger.info("Academic calendar tables verified")
    except (sqlite3.Error, DatabaseError) as e:
        logging.warning(f"Failed to ensure academic calendar tables: {e}")
    finally:
        if conn:
            conn.close()

    # Ensure email messaging schema matches admin expectations
    try:
        logger.info("Ensuring messaging/email schema...")
        from education_system.post_18.university_system.infrastructure.email.email_db_utilities import initialize_email_db
        initialize_email_db()
        logger.info("Messaging tables verified")
    except (sqlite3.Error, DatabaseError) as e:
        logging.warning(f"Failed to ensure messaging tables: {e}")

    try:
        logger.info("Initializing course management database...")
        from education_system.post_18.university_system.modules.domain.academics.services.course_management import initialize_enhanced_database
        if initialize_enhanced_database():
            logger.info("Course management database initialized")
        else:
            logger.warning("Course management database initialization failed")
    except (ValueError, TypeError, ValidationError) as e:
        logging.warning(f"Failed to initialize course management database: {e}")

    try:
        logger.info("Initializing assignment submission system...")
        if init_assignment_system():
            logger.info("Assignment submission system initialized")
        else:
            logger.warning("Assignment submission system initialization failed")
    except (ValueError, TypeError, ValidationError) as e:
        logging.warning(f"Failed to initialize assignment system: {e}")

    # FIX THE ACCOMMODATION SCHEMA IMMEDIATELY AFTER MAIN DB INIT
    logger.info("Fixing accommodation database schema...")
    fix_accommodation_schema()

    logger.info("Fixing support database schema...")
    fix_support_database_schema()

    # Initialize user authentication database to ensure users table has correct schema
    global auth
    if auth is None:
        auth = get_auth()
        if auth is None:
            # Create if doesn't exist
            auth = UserAuth()
            set_auth(auth)

    # Wait a moment to ensure the main database is fully initialized
    time.sleep(0.1)

    # Ensure communication system integration
    ensure_communication_integration_on_startup()

    # Initialize other databases one by one (ONLY ONCE)
    databases = [
        ('parent portal', integrate_parent_portal_with_main),
        ('library', init_library_db),
        ('parking', init_parking_db),
        ('alumni', init_alumni_db),
        ('restaurant', init_restaurant_db),
        ('internship', init_internship_db),
        ('helpdesk', init_helpdesk_db),
        ('student union', init_student_union_db),
        ('finance', initialize_finance),  # Initialize finance here, after DB_PATH is set
        ('housing accommodation', init_housing_db),
        ('university shop', init_shop_db),
        ('trip management', init_trip_db),
        ('charity shop', init_charity_shop_db),
        ('cafe system', init_cafe_db),
        ('takeaway system', init_takeaway_db),
        ('grocery shop', init_grocery_db),
        ('staff hr', init_staff_hr_db),
    ]

    init_integration_tables()

    for db_name, init_func in databases:
        try:
            logger.info(f"Initializing {db_name} database...")
            init_func()
            time.sleep(0.05)  # Small delay between database initializations
        except (ValueError, TypeError, ValidationError) as e:
            logging.warning(f"Failed to initialize {db_name} database: {e}")
            # Continue with other databases instead of failing completely

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS chatbot_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL,
            message TEXT NOT NULL,
            response TEXT NOT NULL,
            intent TEXT,
            confidence REAL,
            timestamp TEXT NOT NULL,
            session_id TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        conn.commit()
        conn.close()
        logger.info("Chatbot conversations table created")
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error creating chatbot table: {e}")

    # Initialize chatbot integration
    try:
        if initialize_chatbot_integration():
            logger.info("Chatbot integration initialized")
        else:
            logger.warning("Chatbot integration not available")
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Chatbot integration error: {e}")


    # Initialize communication dashboard (ONLY ONCE)
    try:
        logger.info("Initializing communication dashboard...")
        set_communication_auth(auth)
        integrate_communication_dashboard_with_main()
        time.sleep(0.05)
    except (ValueError, TypeError, ValidationError) as e:
        logging.warning(f"Failed to initialize communication dashboard: {e}")

    # Initialize AI detector (ONLY ONCE)
    try:
        logger.info("Initializing AI detector...")
        integrate_ai_detector_with_main()
        time.sleep(0.05)
    except (ValueError, TypeError, ValidationError) as e:
        logging.warning(f"Failed to initialize AI detector: {e}")

    # Mark initialization as complete
    init_all_databases._initialization_complete = True

    logger.info("All databases initialization completed!")
    return True


def init_auth_for_modules():
    global auth
    if auth:
        # Set global auth instance for modules that can read it
        set_auth_instance(auth)

        # Configure existing modules with auth
        set_student_union_auth(auth)   # student_union
        set_finance_auth(auth)         # finance
        set_internship_auth(auth)      # internship
        set_accommodation_auth(auth)   # housing accommodation
        # Communication dashboard exposes its auth setter via admin module
        set_communication_auth(auth)
        try:
            from education_system.post_18.university_system.infrastructure.email import email_service
            import education_system.post_18.university_system.infrastructure.email.admin as email_admin
            # Mirror worker state into admin module to avoid optional-import NameErrors
            if not hasattr(email_admin, "worker_threads"):
                email_admin.worker_threads = email_service.worker_threads
            if not hasattr(email_admin, "email_queue"):
                email_admin.email_queue = email_service.email_queue
            if not hasattr(email_admin, "stop_email_workers"):
                email_admin.stop_email_workers = email_service.stop_email_workers
        except (AttributeError, ImportError) as email_link_error:
            logging.debug(f"Skipping email worker linkage: {email_link_error}")
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management import set_auth as set_restaurant_auth
        set_restaurant_auth(auth)
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management import set_auth as set_parking_auth
        set_parking_auth(auth)
        from education_system.post_18.university_system.modules.domain.academics.services.library.settings import set_auth as set_library_auth
        set_library_auth(auth)
        from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management import set_auth as set_alumni_auth
        set_alumni_auth(auth)
        from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support import set_auth as set_student_support_auth
        set_student_support_auth(auth)
        set_medical_accommodation_auth(auth)   # medical accommodation
        from education_system.post_18.university_system.modules.domain.commerce.services.shop_management import set_auth as set_shop_auth
        set_trip_auth(auth)
        set_shop_auth(auth)
        set_charity_shop_auth(auth)    # charity shop
        set_cafe_auth(auth)            # cafe system
        set_takeaway_auth(auth)        # takeaway system
        set_grocery_auth(auth)         # grocery shop
        set_calendar_auth(auth)        # academic calendar
        setup_chatbot_permissions()

        # Wire the Student Union modules that keep their own module-level `auth`
        for m in (su_club, su_event, su_fac, su_admin, su_elec, su_fin):
            if hasattr(m, "set_auth"):
                m.set_auth(auth)

        # Ensure calendar permissions exist
        try:
            ensure_calendar_permissions()
        except (AuthenticationError, PermissionDeniedError) as e:
            logging.warning(f"Could not ensure calendar permissions: {e}")


__all__ = [
    'get_db_connection',
    'safe_db_operation_with_retry',
    'enhanced_db_operation',
    'handle_database_error',
    'fix_accommodation_schema',
    'fix_parent_portal_database',
    'fix_ai_detector_database_schema',
    'fix_support_database_schema',
    'fix_duplicate_emails',
    'silent_integrity_check',
    'validate_database_integrity',
    'validate_database_integrity_with_admin_context',
    'emergency_fix_database',
    'cleanup_database_on_startup',
    'cleanup_database_connections',
    'init_db',
    'init_integration_tables',
    'init_all_databases',
    'init_auth_for_modules',
]
