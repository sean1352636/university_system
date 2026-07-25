"""
Legacy database utilities maintained for backward compatibility.

This module now delegates its database connectivity to the central
wrapper in ``refactored.database.db``.  The ``sqlite3`` import has
been replaced with the proxy provided by that module, and the
``DatabaseManager`` class defaults to using the shared database file
in ``db_files/student_records.db``.  Code throughout the project
should import ``sqlite3`` and ``DatabaseManager`` from
``refactored.database.db``, but this module remains to support any
legacy imports.
"""

import time
import logging
from typing import Optional, Iterable
from pathlib import Path

# Import our centralised sqlite3 proxy and default path
from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH

# Import i18n for translations
from education_system.systems.university.infrastructure.i18n import get_text as _t

class DatabaseManager:
    """
    Context manager for database connections with retry logic.

    This legacy implementation defers to the project‑wide ``sqlite3``
    proxy and defaults to the central database path when none is
    supplied.  It mirrors the interface of the newer
    :class:`refactored.database.db.DatabaseManager` but remains
    available to avoid breaking imports from older modules.
    """

    def __init__(self, db_path: Optional[str] = None, max_retries: int = 5, retry_delay: float = 0.1) -> None:
        # Use the shared default database path if db_path is None or matches the legacy name
        self.db_path: str = db_path or DEFAULT_DB_PATH
        self.max_retries: int = max_retries
        self.retry_delay: float = retry_delay
        self.conn = None  # type: Optional[sqlite3.Connection]
        self.cursor = None  # type: Optional[sqlite3.Cursor]

    def __enter__(self):
        for attempt in range(self.max_retries):
            try:
                self.conn = sqlite3.connect(self.db_path, timeout=10.0)
                self.conn.row_factory = sqlite3.Row
                self.cursor = self.conn.cursor()
                return self
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < self.max_retries - 1:
                    logging.warning(f"Database locked, retrying in {self.retry_delay}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(self.retry_delay)
                    self.retry_delay *= 2  # Exponential backoff
                else:
                    raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()
        return False

    def execute(self, query, params=None):
        if params:
            return self.cursor.execute(query, params)
        return self.cursor.execute(query)

    def executemany(self, query, params):
        return self.cursor.executemany(query, params)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()


# Updated init_db function using the DatabaseManager
def init_db():
    """Initialize database with all required tables on startup"""
    try:
        # Import the comprehensive database setup
        from education_system.systems.university.__init__.scripts.setup_unified_database import create_unified_database

        # Convert DEFAULT_DB_PATH to Path object if it's a string
        db_path = Path(DEFAULT_DB_PATH) if isinstance(DEFAULT_DB_PATH, str) else DEFAULT_DB_PATH

        # Check if database exists and has tables
        db_needs_setup = False
        if not db_path.exists():
            db_needs_setup = True
            logging.info("Database file not found. Creating new database...")
        else:
            # Check if database has required domain tables
            required_tables = {'modules', 'student_modules', 'payments', 'assignments', 'support_tickets'}
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = {row[0] for row in cursor.fetchall()}
            finally:
                conn.close()

            missing = required_tables - tables
            if missing:
                db_needs_setup = True
                logging.info("Database missing tables %s. Running schema setup...", missing)

        if db_needs_setup:
            # Run the comprehensive database setup
            create_unified_database()

            # Initialize all schemas from centralized schema file
            from education_system.systems.university.infrastructure.database.schemas.misc_schemas import initialize_all_schemas
            initialize_all_schemas()

            # Seed default staff profiles (may fail if staff_profiles table
            # was not created by the active schema set — that's OK)
            try:
                from education_system.systems.university.__init__.scripts.setup_unified_database import seed_default_staff
                seed_default_staff()
            except Exception:
                logging.debug("Skipped seeding staff profiles (table may not exist)")

            logging.info("Database initialized successfully with all tables!")
            print("✅ " + _t("database.init_success"))
            return True
        # Ensure student_modules has module_code column (migration for older schemas)
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cols = [row[1] for row in conn.execute("PRAGMA table_info(student_modules)").fetchall()]
                migrations = {
                    'module_code': 'TEXT',
                    'module_name': 'TEXT',
                    'module_type': "TEXT DEFAULT 'Standard'",
                    'completion_date': 'TEXT',
                }
                for col, typedef in migrations.items():
                    if col not in cols:
                        conn.execute(f"ALTER TABLE student_modules ADD COLUMN {col} {typedef}")
                        logging.info("Added missing column student_modules.%s", col)
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logging.debug("student_modules migration check skipped")

        # Cross-system identity link (shared.cross_system.student_journey).
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                stu_cols = [row[1] for row in conn.execute(
                    "PRAGMA table_info(students)").fetchall()]
                if "journey_id" not in stu_cols:
                    conn.execute("ALTER TABLE students ADD COLUMN journey_id TEXT")
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_students_journey_id "
                        "ON students(journey_id)"
                    )
                    logging.info("Added students.journey_id column")
                # Entry qualifications populated by
                # ``on_progression_accepted`` when results day fires
                # ``student.progression.accepted``. JSON of
                # {qualification: grade}.
                if "entry_qualifications" not in stu_cols:
                    conn.execute(
                        "ALTER TABLE students ADD COLUMN "
                        "entry_qualifications TEXT"
                    )
                if "conditions_met" not in stu_cols:
                    conn.execute(
                        "ALTER TABLE students ADD COLUMN "
                        "conditions_met INTEGER"
                    )
                # Columns the repository / GUI create paths use but the
                # core_schemas CREATE historically omitted. Backfill them
                # on existing DBs so a fresh and an upgraded DB look the
                # same (and the sixth-form intake / repository.save can
                # write them).
                if "title" not in stu_cols:
                    conn.execute(
                        "ALTER TABLE students ADD COLUMN title TEXT")
                    logging.info("Added students.title column")
                if "registration_datetime" not in stu_cols:
                    conn.execute(
                        "ALTER TABLE students ADD COLUMN "
                        "registration_datetime TEXT")
                    logging.info(
                        "Added students.registration_datetime column")
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logging.debug("students cross-system migrations skipped")

        # Retire the standalone notifications store. The Notifications Hub is
        # now an unread inbox over the `messages` / cross-system tables, and
        # `NotificationsService` (which used to own these tables) has been
        # removed — so drop the whole family once, idempotently, on startup.
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                for _tbl in (
                    "notification_bundle_items", "bundled_notifications",
                    "notification_history", "notification_channels",
                    "notification_preferences", "digests",
                    "notifications", "notifications_old",
                ):
                    conn.execute(f"DROP TABLE IF EXISTS {_tbl}")
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logging.debug("legacy notifications drop skipped")

        if not db_needs_setup:
            logging.info(f"Database already initialized with {len(tables)} tables")
            return True

    except Exception as ex:
        logging.critical(f"Failed to initialize database: {ex}")
        print(_t("common.failed_init_db") + f": {ex}")
        return False

# Legacy init_db_parking function for backward compatibility
def init_db_parking():
    """Legacy function - now handled by comprehensive init_db"""
    try:
        with DatabaseManager() as db:
            # Check if users table exists with expected schema
            db.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in db.fetchall()]

            if not columns:
                print(_t("database.users_table_not_found"))

            # Create students table
            db.execute('''
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

            # Create payments table
            db.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                currency TEXT DEFAULT 'GBP',
                payment_method TEXT,
                gateway_transaction_id TEXT,
                gateway_name TEXT,
                transaction_id TEXT,
                payment_date TEXT,
                status TEXT DEFAULT 'completed',
                notes TEXT,
                created_by TEXT,
                created_at TEXT,
                fraud_score DECIMAL(3,2),
                is_suspicious BOOLEAN DEFAULT 0,
                source_type TEXT,
                reference_id TEXT,
                reference_type TEXT,
                payment_reference TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')

            db.execute('CREATE INDEX IF NOT EXISTS idx_payments_student_id ON payments(student_id)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date)')

            # Create student payment plans table
            db.execute('''
            CREATE TABLE IF NOT EXISTS student_payment_plans (
                payment_plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                template_id INTEGER,
                total_amount DECIMAL(10,2) NOT NULL,
                remaining_amount DECIMAL(10,2) NOT NULL,
                currency TEXT DEFAULT 'GBP',
                status TEXT DEFAULT 'active',
                start_date TEXT NOT NULL,
                next_due_date TEXT,
                setup_fee_paid BOOLEAN DEFAULT 0,
                auto_payment_enabled BOOLEAN DEFAULT 0,
                payment_method_id INTEGER,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (template_id) REFERENCES payment_plan_templates (template_id)
            )
            ''')

            # Create fee types table
            db.execute('''
            CREATE TABLE IF NOT EXISTS fee_types (
                fee_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                fee_name TEXT NOT NULL,
                description TEXT,
                is_recurring BOOLEAN DEFAULT 0,
                academic_year TEXT,
                is_late_fee BOOLEAN DEFAULT 0,
                late_fee_calculation TEXT,
                late_fee_amount DECIMAL(10,2),
                grace_period_days INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
            ''')

            # Create student fees table
            db.execute('''
            CREATE TABLE IF NOT EXISTS student_fees (
                student_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                fee_type_id INTEGER NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                currency TEXT DEFAULT 'GBP',
                status TEXT DEFAULT 'unpaid',
                due_date TEXT,
                last_reminder_sent TEXT,
                reminder_count INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (fee_type_id) REFERENCES fee_types (fee_type_id)
            )
            ''')

            db.execute('CREATE INDEX IF NOT EXISTS idx_student_fees_student_id ON student_fees(student_id)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_student_fees_status ON student_fees(status)')

            # Create scholarships table
            db.execute('''
            CREATE TABLE IF NOT EXISTS scholarships (
                scholarship_id INTEGER PRIMARY KEY AUTOINCREMENT,
                scholarship_name TEXT NOT NULL,
                description TEXT,
                amount DECIMAL(10,2),
                academic_year TEXT,
                criteria TEXT,
                deadline TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
            ''')

            # Create student financial aid table
            db.execute('''
            CREATE TABLE IF NOT EXISTS student_financial_aid (
                aid_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                aid_type_id INTEGER NOT NULL,
                awarded_amount DECIMAL(10,2) NOT NULL,
                disbursed_amount DECIMAL(10,2) DEFAULT 0,
                remaining_amount DECIMAL(10,2) NOT NULL,
                currency TEXT DEFAULT 'GBP',
                status TEXT DEFAULT 'pending',
                application_date TEXT,
                approval_date TEXT,
                disbursement_schedule TEXT,
                repayment_start_date TEXT,
                monthly_payment_amount DECIMAL(10,2),
                total_repaid DECIMAL(10,2) DEFAULT 0,
                approved_by TEXT,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (aid_type_id) REFERENCES financial_aid_types (aid_type_id)
            )
            ''')

            # Create budget plans table
            db.execute('''
            CREATE TABLE IF NOT EXISTS budget_plans (
                budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_name TEXT NOT NULL,
                academic_year TEXT NOT NULL,
                currency TEXT DEFAULT 'GBP',
                status TEXT DEFAULT 'draft',
                total_revenue_budget DECIMAL(12,2) DEFAULT 0,
                total_expense_budget DECIMAL(12,2) DEFAULT 0,
                created_by TEXT,
                approved_by TEXT,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            ''')

            # Create parking tables
            db.execute('''
            CREATE TABLE IF NOT EXISTS parking_permits (
                permit_id TEXT PRIMARY KEY,
                user_id INTEGER,
                full_name TEXT,
                email TEXT,
                zone TEXT,
                permit_type TEXT,
                start_date TEXT,
                end_date TEXT,
                active_status TEXT,
                vehicle_id TEXT,
                issue_date TEXT,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            ''')

            db.execute('''
            CREATE TABLE IF NOT EXISTS vehicles (
                vehicle_id TEXT PRIMARY KEY,
                license_plate TEXT NOT NULL,
                make TEXT,
                model TEXT,
                year INTEGER,
                color TEXT,
                vehicle_type TEXT,
                owner_id INTEGER,
                registration_state TEXT,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )
            ''')

            db.execute('''
            CREATE TABLE IF NOT EXISTS parking_lots (
                lot_id TEXT PRIMARY KEY,
                lot_name TEXT,
                location TEXT,
                total_spaces INTEGER,
                available_spaces INTEGER,
                zone TEXT,
                hours_of_operation TEXT
            )
            ''')

            db.execute('''
            CREATE TABLE IF NOT EXISTS parking_spaces (
                space_id TEXT PRIMARY KEY,
                lot_id TEXT,
                space_number TEXT,
                space_type TEXT,
                occupancy_status TEXT,
                reserved_for TEXT,
                FOREIGN KEY (lot_id) REFERENCES parking_lots (lot_id)
            )
            ''')

            db.execute('''
            CREATE TABLE IF NOT EXISTS parking_violations (
                violation_id TEXT PRIMARY KEY,
                vehicle_id TEXT,
                license_plate TEXT,
                violation_type TEXT,
                violation_date TEXT,
                fine_amount REAL,
                payment_status TEXT,
                location TEXT,
                officer_id INTEGER,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
                FOREIGN KEY (officer_id) REFERENCES users(id)
            )
            ''')

            # Check if parking lots already exist
            db.execute('SELECT COUNT(*) FROM parking_lots')
            lot_count = db.fetchone()[0]

            if lot_count == 0:
                # Only insert default parking lots if none exist
                lot_data = [
                    ('L001', 'North Campus Lot', 'North Campus', 200, 200, 'A', '24/7'),
                    ('L002', 'South Campus Lot', 'South Campus', 150, 150, 'B', '24/7'),
                    ('L003', 'East Campus Lot', 'East Campus', 100, 100, 'C', '24/7'),
                    ('L004', 'West Campus Lot', 'West Campus', 80, 80, 'V', '7:00-22:00'),
                    ('L005', 'Central Campus Lot', 'Central Campus', 50, 50, 'H', '24/7')
                ]

                db.executemany(
                    'INSERT INTO parking_lots (lot_id, lot_name, location, total_spaces, available_spaces, zone, hours_of_operation) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    lot_data
                )

                logging.info("Default parking lots created!")
                print(_t("database.parking_lots_created"))

        logging.info("Database initialized successfully!")
        print(_t("database.init_success"))
        return True

    except sqlite3.Error as e:
        logging.error(f"An error occurred while initializing the database: {e}")
        print(_t("database.init_error") + f": {e}")
        return False
    except Exception as ex:
        logging.critical(f"Failed to initialize database: {ex}")
        print(_t("common.failed_init_db") + f": {ex}")
        return False

def cleanup_database_connections():
    """Close any open database connections"""
    import gc
    gc.collect()
