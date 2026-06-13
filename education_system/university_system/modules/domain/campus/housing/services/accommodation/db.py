import logging
from datetime import datetime

from education_system.university_system.modules.domain.campus.housing.services.accommodation._common import (
    sqlite3, DB_PATH, TEMPLATES_TABLE, get_connection, get_text,
)


def init_accommodation_db():
    """Initialize accommodation, audit, and template tables with better error handling."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Create accommodations table with additional fields
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accommodations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    accommodation_type TEXT NOT NULL,
                    description TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    status TEXT DEFAULT 'active',
                    approved_by TEXT,
                    approval_date TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            ''')

            # Create audit log table with more detailed tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    accommodation_id INTEGER,
                    details TEXT,
                    ip_address TEXT,
                    timestamp TEXT NOT NULL
                )
            ''')

            # Create templates table
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS [" + TEMPLATES_TABLE + "] ("
                " name TEXT PRIMARY KEY,"
                " accommodation_type TEXT NOT NULL,"
                " description TEXT,"
                " start_offset_days INTEGER,"
                " duration_days INTEGER,"
                " created_by TEXT,"
                " created_at TEXT,"
                " updated_at TEXT"
                ")"
            )

            # Create accommodation types table for standardized types
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accommodation_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type_name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    requires_approval BOOLEAN DEFAULT 0,
                    max_duration_days INTEGER,
                    created_at TEXT
                )
            ''')

            # Add some default accommodation types if the table is empty
            cursor.execute('SELECT COUNT(*) FROM accommodation_types')
            if cursor.fetchone()[0] == 0:
                default_types = [
                    ('Extended Time', 'Additional time for assignments or exams', 0, 365),
                    ('Alternate Format', 'Materials provided in alternate formats', 0, 365),
                    ('Note-Taking', 'Note-taking assistance in classes', 0, 365),
                    ('Assistive Technology', 'Access to specialized technology', 1, 365),
                    ('Flexible Attendance', 'Modified attendance requirements', 1, 180)
                ]
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for type_name, desc, req_approval, max_days in default_types:
                    cursor.execute('''
                        INSERT INTO accommodation_types
                        (type_name, description, requires_approval, max_duration_days, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (type_name, desc, req_approval, max_days, now))

            # Accommodation documents now use the unified documents table
            # with source_type = 'accommodation'
            # No separate accommodation_documents table needed

            conn.commit()
            logging.info("Accommodation database initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize accommodation database: {e}")
        print(get_text("housing.accommodation.db.error_init_failed", "Error: Could not initialize accommodation database. Details: {error}").format(error=e))
        # Attempt to create essential tables as fallback
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS accommodations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        accommodation_type TEXT NOT NULL,
                        description TEXT,
                        start_date TEXT,
                        end_date TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        action TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        accommodation_id INTEGER,
                        timestamp TEXT NOT NULL
                    )
                ''')
                conn.commit()
                logging.info("Minimal accommodation database created as fallback")
                print(get_text("housing.accommodation.db.created_minimal_tables", "Created minimal accommodation database tables"))
        except Exception as fallback_e:
            logging.critical(f"Fallback database creation also failed: {fallback_e}")
            print(get_text("housing.accommodation.db.critical_error_minimal_tables", "Critical Error: Could not create even minimal database tables: {error}").format(error=fallback_e))


def migrate_audit_log_schema():
    """Migrate the audit_log table to include missing columns."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Check current schema of audit_log table
            cursor.execute("PRAGMA table_info(audit_log)")
            columns = [row[1] for row in cursor.fetchall()]

            print(get_text("housing.accommodation.db.current_columns", "Current audit_log columns:"), columns)

            # Check if accommodation_id column exists
            if 'accommodation_id' not in columns:
                print(get_text("housing.accommodation.db.adding_column", "Adding missing {column} column...").format(column="accommodation_id"))
                cursor.execute('ALTER TABLE audit_log ADD COLUMN accommodation_id INTEGER')

            # Check if details column exists
            if 'details' not in columns:
                print(get_text("housing.accommodation.db.adding_column", "Adding missing {column} column...").format(column="details"))
                cursor.execute('ALTER TABLE audit_log ADD COLUMN details TEXT')

            # Check if ip_address column exists
            if 'ip_address' not in columns:
                print(get_text("housing.accommodation.db.adding_column", "Adding missing {column} column...").format(column="ip_address"))
                cursor.execute('ALTER TABLE audit_log ADD COLUMN ip_address TEXT')

            conn.commit()
            print(get_text("housing.accommodation.db.migration_complete", "Schema migration completed successfully!"))

            # Verify the new schema
            cursor.execute("PRAGMA table_info(audit_log)")
            new_columns = [row[1] for row in cursor.fetchall()]
            print(get_text("housing.accommodation.db.updated_columns", "Updated audit_log columns:"), new_columns)

    except Exception as e:
        logging.error(f"Error migrating audit_log schema: {e}")
        print(get_text("housing.accommodation.error.migrating_schema", "Error migrating schema: {error}").format(error=e))
        return False

    return True


def fix_accommodation_db_schema():
    """Fix any schema issues in the accommodation database."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Check if the accommodations table exists and has all required columns
            cursor.execute("PRAGMA table_info(accommodations)")
            acc_columns = [row[1] for row in cursor.fetchall()]

            print(get_text("housing.accommodation.db.current_acc_columns", "Current accommodations columns:"), acc_columns)

            # Required columns for accommodations table
            required_acc_columns = [
                ('status', 'TEXT DEFAULT "active"'),
                ('approved_by', 'TEXT'),
                ('approval_date', 'TEXT'),
                ('notes', 'TEXT')
            ]

            for col_name, col_def in required_acc_columns:
                if col_name not in acc_columns:
                    print(get_text("housing.accommodation.db.adding_column_to_table", "Adding missing column {column} to accommodations table...").format(column=col_name))
                    from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608
                    validate_identifier(col_name, "column")
                    cursor.execute("ALTER TABLE accommodations ADD COLUMN [" + col_name + "] " + col_def)

            # Check if accommodation_types table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='accommodation_types'
            """)

            if not cursor.fetchone():
                print(get_text("housing.accommodation.db.creating_table", "Creating missing {table} table...").format(table="accommodation_types"))
                cursor.execute('''
                    CREATE TABLE accommodation_types (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        type_name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        requires_approval BOOLEAN DEFAULT 0,
                        max_duration_days INTEGER,
                        created_at TEXT
                    )
                ''')

                # Add default types
                default_types = [
                    ('Extended Time', 'Additional time for assignments or exams', 0, 365),
                    ('Alternate Format', 'Materials provided in alternate formats', 0, 365),
                    ('Note-Taking', 'Note-taking assistance in classes', 0, 365),
                    ('Assistive Technology', 'Access to specialized technology', 1, 365),
                    ('Flexible Attendance', 'Modified attendance requirements', 1, 180)
                ]
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for type_name, desc, req_approval, max_days in default_types:
                    cursor.execute('''
                        INSERT INTO accommodation_types
                        (type_name, description, requires_approval, max_duration_days, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (type_name, desc, req_approval, max_days, now))

            # Accommodation documents now use the unified documents table
            # with source_type = 'accommodation' — no separate table needed

            # Check if accommodation_templates table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='accommodation_templates'
            """)

            if not cursor.fetchone():
                print(get_text("housing.accommodation.db.creating_table", "Creating missing {table} table...").format(table="accommodation_templates"))
                cursor.execute('''
                    CREATE TABLE accommodation_templates (
                        name TEXT PRIMARY KEY,
                        accommodation_type TEXT NOT NULL,
                        description TEXT,
                        start_offset_days INTEGER,
                        duration_days INTEGER,
                        created_by TEXT,
                        created_at TEXT,
                        updated_at TEXT
                    )
                ''')

            conn.commit()
            print(get_text("housing.accommodation.db.schema_fix_complete", "Accommodation database schema fix completed!"))

    except Exception as e:
        logging.error(f"Error fixing accommodation database schema: {e}")
        print(get_text("housing.accommodation.error.fixing_schema", "Error fixing schema: {error}").format(error=e))
        return False

    return True


def verify_database_schema():
    """Verify that all required tables and columns exist."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get list of all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            print(get_text("housing.accommodation.db.available_tables", "Available tables:"), tables)

            # Check each table's schema
            for table in tables:
                from education_system.university_system.core.sql_safety import validate_table_name
                validated_table = validate_table_name(table, conn=conn)
                cursor.execute("PRAGMA table_info([" + validated_table + "])")
                columns = cursor.fetchall()
                print(f"\n{table} " + get_text("housing.accommodation.db.table_columns", "table columns:"))
                for col in columns:
                    print(f"  - {col[1]} ({col[2]})")

    except Exception as e:
        print(get_text("housing.accommodation.error.verifying_schema", "Error verifying schema: {error}").format(error=e))
