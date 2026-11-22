from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation import common as _common
from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation.common import (
    sqlite3, datetime,
    get_text, get_connection,
)

# Database initialization
def init_housing_db():
    """Initialize the housing accommodation database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create housing_buildings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_buildings (
            building_id TEXT PRIMARY KEY,
            building_name TEXT NOT NULL,
            address TEXT NOT NULL,
            campus_location TEXT NOT NULL,
            total_rooms INTEGER NOT NULL,
            available_rooms INTEGER NOT NULL,
            has_elevator BOOLEAN DEFAULT 0,
            has_accessible_rooms BOOLEAN DEFAULT 0,
            has_kitchen BOOLEAN DEFAULT 0,
            has_laundry BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        ''')

        # Create housing_rooms table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_rooms (
            room_id TEXT PRIMARY KEY,
            building_id TEXT NOT NULL,
            room_number TEXT NOT NULL,
            floor_number INTEGER NOT NULL,
            room_type TEXT NOT NULL,
            max_occupants INTEGER NOT NULL,
            current_occupants INTEGER DEFAULT 0,
            is_accessible BOOLEAN DEFAULT 0,
            status TEXT NOT NULL,
            monthly_rent REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (building_id) REFERENCES housing_buildings (building_id)
        )
        ''')

        # Create housing_applications table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_applications (
            application_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            application_date TEXT NOT NULL,
            preferred_building_id TEXT,
            preferred_room_type TEXT NOT NULL,
            requested_move_in_date TEXT NOT NULL,
            requested_duration_months INTEGER NOT NULL,
            special_requirements TEXT,
            status TEXT NOT NULL,
            notes TEXT,
            reviewed_by TEXT,
            review_date TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (preferred_building_id) REFERENCES housing_buildings (building_id)
        )
        ''')

        # Create housing_assignments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_assignments (
            assignment_id TEXT PRIMARY KEY,
            application_id TEXT,
            student_id TEXT NOT NULL,
            room_id TEXT NOT NULL,
            move_in_date TEXT NOT NULL,
            planned_move_out_date TEXT NOT NULL,
            actual_move_out_date TEXT,
            contract_number TEXT UNIQUE,
            monthly_rent REAL NOT NULL,
            status TEXT NOT NULL,
            assigned_by TEXT NOT NULL,
            tdp_scheme TEXT,
            tdp_scheme_reference TEXT,
            tdp_protected_at TEXT,
            tdp_prescribed_info_sent_at TEXT,
            tdp_deadline TEXT,
            tdp_exempt_reason TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (application_id) REFERENCES housing_applications (application_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id)
        )
        ''')
        # Idempotent TDP + interest column guards for assignments tables created
        # before the columns were defined.
        try:
            cursor.execute("PRAGMA table_info(housing_assignments)")
            asg_cols = {row[1] for row in cursor.fetchall()}
            text_cols = (
                'tdp_scheme', 'tdp_scheme_reference', 'tdp_protected_at',
                'tdp_prescribed_info_sent_at', 'tdp_deadline', 'tdp_exempt_reason',
                'deposit_interest_last_accrual_date', 'deposit_interest_policy',
                'deposit_state',
            )
            real_cols = ('deposit_interest_rate', 'deposit_interest_accrued')
            for col in text_cols:
                if col not in asg_cols:
                    # db-audit: ignore[DBW001] - literal collection
                    cursor.execute(
                        f"ALTER TABLE housing_assignments ADD COLUMN {col} TEXT"
                    )
            for col in real_cols:
                if col not in asg_cols:
                    # db-audit: ignore[DBW001] - literal collection
                    cursor.execute(
                        f"ALTER TABLE housing_assignments ADD COLUMN {col} REAL DEFAULT 0"
                    )
        except sqlite3.Error:
            pass

        # Audit trail of deposit lifecycle transitions so disputes about
        # "when did this become Disputed / Refunded" can be answered.
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_deposit_state_log (
            log_id TEXT PRIMARY KEY,
            assignment_id TEXT NOT NULL,
            from_state TEXT,
            to_state TEXT NOT NULL,
            reason TEXT,
            actor TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (assignment_id) REFERENCES housing_assignments (assignment_id)
        )
        ''')

        # Audit trail for every accrual slice so the running balance on the
        # assignment can be reconstructed and reconciled.
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_deposit_interest_accruals (
            accrual_id TEXT PRIMARY KEY,
            assignment_id TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            principal REAL NOT NULL,
            annual_rate REAL NOT NULL,
            days INTEGER NOT NULL,
            amount REAL NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (assignment_id) REFERENCES housing_assignments (assignment_id)
        )
        ''')

        # Housing payments use the unified 'payments' table with source_type = 'housing'.
        # The baseline migration defines payment_type, but on older or test DBs that
        # column may be missing. Add it idempotently so record_payment's INSERT
        # (which now includes payment_type) doesn't fail.
        try:
            cursor.execute("PRAGMA table_info(payments)")
            payment_cols = {row[1] for row in cursor.fetchall()}
            if payment_cols and 'payment_type' not in payment_cols:
                cursor.execute("ALTER TABLE payments ADD COLUMN payment_type TEXT")
        except sqlite3.Error:
            # Table doesn't exist yet on this DB — the finance layer will create it
            # with payment_type included.
            pass

        # Create housing_maintenance_requests table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_maintenance_requests (
            request_id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            student_id TEXT NOT NULL,
            request_date TEXT NOT NULL,
            issue_type TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            assigned_to TEXT,
            scheduled_date TEXT,
            completion_date TEXT,
            feedback TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Create inspections table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_inspections (
            inspection_id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            inspector TEXT NOT NULL,
            inspection_date TEXT NOT NULL,
            inspection_type TEXT NOT NULL,
            status TEXT NOT NULL,
            findings TEXT,
            action_required TEXT,
            follow_up_date TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id)
        )
        ''')

        # Deposit deductions — itemised charges raised against a held deposit at
        # move-out. Each row references the deposit payment being drawn down and,
        # where applicable, the move-out inspection that justifies the charge.
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_deposit_deductions (
            deduction_id TEXT PRIMARY KEY,
            assignment_id TEXT NOT NULL,
            deposit_payment_id TEXT,
            inspection_id TEXT,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Proposed',
            acknowledgement_status TEXT NOT NULL DEFAULT 'Pending',
            acknowledged_at TEXT,
            dispute_reason TEXT,
            dispute_resolution_notes TEXT,
            dispute_resolved_by TEXT,
            dispute_resolved_at TEXT,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            applied_at TEXT,
            FOREIGN KEY (assignment_id) REFERENCES housing_assignments (assignment_id),
            FOREIGN KEY (inspection_id) REFERENCES housing_inspections (inspection_id)
        )
        ''')
        # Idempotent column guards for DBs created before each column existed.
        try:
            cursor.execute("PRAGMA table_info(housing_deposit_deductions)")
            cols = {row[1] for row in cursor.fetchall()}
            adds = [
                ('status', "TEXT NOT NULL DEFAULT 'Proposed'"),
                ('applied_at', "TEXT"),
                ('acknowledgement_status', "TEXT NOT NULL DEFAULT 'Pending'"),
                ('acknowledged_at', "TEXT"),
                ('dispute_reason', "TEXT"),
                ('dispute_resolution_notes', "TEXT"),
                ('dispute_resolved_by', "TEXT"),
                ('dispute_resolved_at', "TEXT"),
            ]
            for col, decl in adds:
                if col not in cols:
                    # db-audit: ignore[DBW001] - literal collection
                    cursor.execute(
                        f"ALTER TABLE housing_deposit_deductions ADD COLUMN {col} {decl}"
                    )
        except sqlite3.Error:
            pass

        # Create inventory items table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS housing_inventory (
            item_id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            item_type TEXT NOT NULL,
            condition TEXT NOT NULL,
            acquisition_date TEXT,
            status TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id)
        )
        ''')

        # No sample residences are created. An empty housing system is a real
        # state: staff add buildings and rooms through Building Management
        # (CLI menu 1, GUI "Buildings"/"Rooms"), including a CSV room import.
        # The four US-style halls this used to invent ("Freshman Dormitory",
        # "123 Campus Drive", random occupancy and rent) are removed from an
        # existing database by tools/university/remove_seeded_housing.py.

        # Occupancy is derived from occupying assignments (Active/Pending),
        # never stored as a typed-in number: triggers keep
        # housing_rooms.current_occupants equal to that count, and the resync
        # corrects any value written before the triggers existed.
        try:
            from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation.room_setup import (
                install_occupancy_triggers, resync_room_occupancy,
            )
            install_occupancy_triggers(cursor)
            corrected = resync_room_occupancy(cursor)
            if corrected:
                import logging
                logging.getLogger(__name__).info(
                    "Re-derived occupancy for %d room(s) from housing assignments",
                    corrected)
        except sqlite3.Error as e:
            import logging
            logging.getLogger(__name__).warning(
                "Occupancy triggers not installed: %s", e)

        # ── Mirror housing_buildings into the unified `buildings` table
        # ──────────────────────────────────────────────────────────────
        # Facility Management reads from `buildings`; housing wants its
        # residences to show up there with building_type='Residence'.
        # We keep housing_buildings as the housing-specific store but
        # mirror name/address/total_rooms via triggers so the two never
        # drift. building_code holds the housing TEXT id so updates and
        # deletes can match the right row.
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS buildings (
            building_id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_name TEXT NOT NULL,
            building_code TEXT UNIQUE NOT NULL,
            address TEXT,
            total_floors INTEGER,
            total_rooms INTEGER,
            building_type TEXT,
            year_built INTEGER,
            last_renovation_year INTEGER,
            accessibility_features TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # One-time backfill of pre-existing housing rows.
        cursor.execute('''
        INSERT OR IGNORE INTO buildings
            (building_name, building_code, address, total_rooms,
             building_type, is_active, created_at)
        SELECT building_name, building_id, address, total_rooms,
               'Residence', 1, created_at
        FROM housing_buildings
        ''')

        cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS housing_buildings_mirror_insert
        AFTER INSERT ON housing_buildings
        BEGIN
            INSERT OR IGNORE INTO buildings
                (building_name, building_code, address, total_rooms,
                 building_type, is_active, created_at)
            VALUES
                (NEW.building_name, NEW.building_id, NEW.address,
                 NEW.total_rooms, 'Residence', 1, NEW.created_at);
        END;
        ''')

        cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS housing_buildings_mirror_update
        AFTER UPDATE ON housing_buildings
        BEGIN
            UPDATE buildings
               SET building_name = NEW.building_name,
                   address       = NEW.address,
                   total_rooms   = NEW.total_rooms
             WHERE building_code = OLD.building_id;
        END;
        ''')

        cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS housing_buildings_mirror_delete
        AFTER DELETE ON housing_buildings
        BEGIN
            DELETE FROM buildings
             WHERE building_code = OLD.building_id
               AND building_type = 'Residence';
        END;
        ''')

        # Inspection statuses: fold the vocabulary the GUI used to write onto
        # the canonical one shared by both interfaces. Idempotent — after the
        # first run these UPDATEs match nothing — so it is safe to leave in
        # init. Without it, rows written by the old GUI stay invisible to the
        # CLI's status filters and vice versa.
        try:
            from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation.inspections import (
                LEGACY_STATUS_MAP,
            )
            renamed = 0
            for legacy, canonical in LEGACY_STATUS_MAP.items():
                cursor.execute(
                    'UPDATE housing_inspections SET status = ? WHERE status = ?',
                    (canonical, legacy))
                renamed += cursor.rowcount or 0
            if renamed:
                import logging
                logging.getLogger(__name__).info(
                    "Normalised %d inspection status value(s) to the canonical set",
                    renamed)
        except sqlite3.Error as e:
            import logging
            logging.getLogger(__name__).warning(
                "Inspection status normalisation skipped: %s", e)

        conn.commit()
        conn.close()
        print(get_text("housing.db_init_success"))
        return True

    except sqlite3.Error as e:
        print(get_text("housing.common.database_error", error=str(e)))
        return False
    except Exception as e:
        print(get_text("housing.db_init_error", error=str(e)))
        return False
