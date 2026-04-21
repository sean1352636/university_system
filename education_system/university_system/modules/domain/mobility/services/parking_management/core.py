import logging
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.logging.log_config import configure_logging, get_log_file
from education_system.university_system.modules.shared.utils.i18n import get_text

# Alias for convenience
_t = get_text

# Configure logging
log_path = get_log_file("permit_system.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)

logger = configure_logging(name=__name__)

# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)

def init_db():
    conn = None
    try:
        # 1) Open the single student_records database
        conn = get_connection()
        # 2) Turn on FK checks
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()

        # 3) Ensure users table exists (main.py should normally create it first)
        cursor.execute("PRAGMA table_info(users)")
        if not cursor.fetchall():
            logging.info("users table missing – creating it here")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    UNIQUE NOT NULL,
                first_name  TEXT    NOT NULL,
                last_name   TEXT    NOT NULL,
                email       TEXT    UNIQUE NOT NULL,
                role        TEXT    NOT NULL,
                student_id  TEXT,
                created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
            ''')

        # 4) Vehicles table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            vehicle_id         TEXT    PRIMARY KEY,
            license_plate      TEXT    NOT NULL,
            make               TEXT,
            model              TEXT,
            year               INTEGER,
            color              TEXT,
            vehicle_type       TEXT,
            owner_id           INTEGER,
            registration_state TEXT,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        )
        ''')

        # 5) Parking permits
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_permits (
            permit_id     TEXT    PRIMARY KEY,
            user_id       INTEGER,
            full_name     TEXT,
            email         TEXT,
            zone          TEXT,
            permit_type   TEXT,
            start_date    TEXT,
            end_date      TEXT,
            active_status TEXT,
            vehicle_id    TEXT,
            issue_date    TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
            FOREIGN KEY (user_id)    REFERENCES users(id)
        )
        ''')

        # 6) Parking lots
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_lots (
            lot_id              TEXT    PRIMARY KEY,
            lot_name            TEXT,
            location            TEXT,
            total_spaces        INTEGER,
            available_spaces    INTEGER,
            zone                TEXT,
            hours_of_operation  TEXT
        )
        ''')

        # 7) Parking spaces
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_spaces (
            space_id         TEXT    PRIMARY KEY,
            lot_id           TEXT,
            space_number     TEXT,
            space_type       TEXT,
            occupancy_status TEXT,
            reserved_for     TEXT,
            FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id)
        )
        ''')

        # 8) Violations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_violations (
            violation_id    TEXT    PRIMARY KEY,
            vehicle_id      TEXT,
            license_plate   TEXT,
            violation_type  TEXT,
            violation_date  TEXT,
            fine_amount     REAL,
            payment_status  TEXT,
            location        TEXT,
            officer_id      INTEGER,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
            FOREIGN KEY (officer_id) REFERENCES users(id)
        )
        ''')

        # 9) (Optional) Seed default lots if needed
        cursor.execute('SELECT COUNT(*) FROM parking_lots')
        if cursor.fetchone()[0] == 0:
            lot_data = [
                ('L001','North Campus Lot','North Campus',200,200,'A','24/7'),
                ('L002','South Campus Lot','South Campus',150,150,'B','24/7'),
                ('L003','East Campus Lot','East Campus',100,100,'C','24/7'),
                ('L004','West Campus Lot','West Campus',80,80,'V','07:00-22:00'),
                ('L005','Central Campus Lot','Central Campus',50,50,'H','24/7')
            ]
            cursor.executemany(
                'INSERT INTO parking_lots VALUES (?,?,?,?,?,?,?)',
                lot_data
            )
            logging.info("Default parking lots created")

        conn.commit()
        logging.info("Parking DB initialized in student_records.db")
        return True

    except sqlite3.Error as e:
        logging.error(f"Parking init_db() error: {e}")
        print(_t("parking.error.init_db") + f": {e}")
        return False

    finally:
        if conn:
            conn.close()
