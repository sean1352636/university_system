# trip_management package - split from trip_management.py
# All public names are re-exported here for backwards compatibility.

from education_system.university_system.modules.domain.campus.mobility.services.trip_management._common import set_auth, PDF_AVAILABLE, CALENDAR_AVAILABLE, HAS_AUTH

from education_system.university_system.infrastructure.database.db import get_connection, transaction

try:
    from education_system.university_system.core.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

from education_system.university_system.modules.domain.campus.mobility.services.trip_management import database as _database

from education_system.university_system.modules.domain.campus.mobility.services.trip_management.permissions import setup_trip_permissions, setup_report_permissions

from education_system.university_system.modules.domain.campus.mobility.services.trip_management.trips import (
    view_trips_with_calendar,
    create_trip,
    view_trips,
    view_trip_details,
    update_trip,
    delete_trip,
)

from education_system.university_system.modules.domain.campus.mobility.services.trip_management.registrations import (
    register_for_trip,
    view_my_trip_registrations,
    manage_trip_participants,
    update_payment_status,
    update_participant_status,
    remove_participant,
    cancel_trip_registration,
)

from education_system.university_system.modules.domain.campus.mobility.services.trip_management.calendar_integration import (
    create_trip_calendar_event,
    view_trip_events_in_calendar,
)

from education_system.university_system.modules.domain.campus.mobility.services.trip_management.reports import TripReportGenerator, generate_trip_report

from education_system.university_system.modules.domain.campus.mobility.services.trip_management.itinerary import add_trip_itinerary, view_trip_itinerary

from education_system.university_system.modules.domain.campus.mobility.services.trip_management.expenses import (
    manage_trip_expenses,
    add_expense,
    edit_expense,
    delete_expense,
)

from education_system.university_system.modules.domain.campus.mobility.services.trip_management.staff import assign_trip_staff

from education_system.university_system.modules.domain.campus.mobility.services.trip_management.menu import (
    display_trip_management_menu,
    integrate_trip_management_with_main,
    test_report_generation,
    test_trip_management,
)


def get_db_connection(timeout: float = 30.0, max_retries: int = 3):
    """Compatibility wrapper that uses this module's get_connection (patch-friendly)."""
    from education_system.university_system.modules.domain.campus.mobility.services.trip_management import _common

    retry_delay = 0.1
    for attempt in range(max_retries):
        try:
            conn = get_connection(db_path=_common.DEFAULT_DB_PATH, timeout=timeout)
            return conn
        except _common.sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                _common.time.sleep(retry_delay * (2 ** attempt))
                continue
            return None
        except _common.sqlite3.Error:
            return None


def safe_db_operation(operation_func, *args, max_retries: int = 3, **kwargs):
    """Compatibility wrapper for safe_db_operation using local get_db_connection."""
    from education_system.university_system.modules.domain.campus.mobility.services.trip_management import _common

    retry_delay = 0.1
    last_error = None
    for attempt in range(max_retries):
        conn = None
        try:
            conn = get_db_connection(timeout=30.0)
            if not conn:
                last_error = "Failed to establish database connection"
                if attempt < max_retries - 1:
                    _common.time.sleep(retry_delay * (2 ** attempt))
                    continue
                return False
            try:
                result = operation_func(conn, *args, **kwargs)
            except TypeError:
                # Support legacy callables that don't accept a connection argument.
                result = operation_func(*args, **kwargs)
            try:
                conn.commit()
            except Exception:
                pass
            return result
        except Exception as e:  # pragma: no cover - defensive
            last_error = e
            try:
                if conn:
                    conn.rollback()
            except Exception:
                pass
            return False
        finally:
            try:
                if conn:
                    conn.close()
            except Exception:
                pass
    return False


def init_trip_db():
    """Initialize trip management database tables (transaction-based wrapper)."""
    def _create_tables(conn):
        cursor = conn.cursor()
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
        return True

    with transaction() as conn:
        return _create_tables(conn)

if __name__ == "__main__":
    test_report_generation()
    # Run tests
    test_trip_management()
