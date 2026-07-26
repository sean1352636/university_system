from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation import common as _common
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.common import (
    sqlite3, datetime, random,
    get_text, get_connection, generate_id,
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
                    cursor.execute(
                        f"ALTER TABLE housing_assignments ADD COLUMN {col} TEXT"
                    )
            for col in real_cols:
                if col not in asg_cols:
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

        # Fetch the count of buildings to check if we need to create sample data
        cursor.execute('SELECT COUNT(*) FROM housing_buildings')
        building_count = cursor.fetchone()[0]

        # If no buildings exist, create sample data
        if building_count == 0:
            # Add sample buildings
            sample_buildings = [
                ('B001', 'University Residence Hall', '123 Campus Drive', 'North Campus', 100, 35, 1, 1, 1, 1),
                ('B002', 'Graduate Housing Complex', '456 Scholar Avenue', 'South Campus', 80, 20, 1, 1, 1, 1),
                ('B003', 'Freshman Dormitory', '789 College Road', 'East Campus', 150, 50, 0, 1, 0, 1),
                ('B004', 'International House', '321 Global Street', 'West Campus', 60, 15, 1, 1, 1, 1)
            ]

            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for building in sample_buildings:
                cursor.execute('''
                INSERT INTO housing_buildings
                (building_id, building_name, address, campus_location, total_rooms, available_rooms,
                has_elevator, has_accessible_rooms, has_kitchen, has_laundry, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (building[0], building[1], building[2], building[3], building[4], building[5],
                      building[6], building[7], building[8], building[9], timestamp, timestamp))

            # Add sample rooms for each building
            room_types = ['Single', 'Double', 'Triple', 'Suite', 'Studio', 'Apartment']
            statuses = ['Available', 'Occupied', 'Maintenance', 'Reserved']

            for building_id in ['B001', 'B002', 'B003', 'B004']:
                # Define how many rooms to create for this building
                if building_id == 'B001':
                    floors = 4
                    rooms_per_floor = 10
                elif building_id == 'B002':
                    floors = 3
                    rooms_per_floor = 8
                elif building_id == 'B003':
                    floors = 5
                    rooms_per_floor = 15
                else:  # B004
                    floors = 2
                    rooms_per_floor = 10

                for floor in range(1, floors + 1):
                    for room_num in range(1, rooms_per_floor + 1):
                        room_number = f"{floor}{str(room_num).zfill(2)}"
                        room_id = f"{building_id}-{room_number}"
                        room_type = random.choice(room_types)
                        max_occupants = 1 if room_type == 'Single' else 2 if room_type == 'Double' else 3 if room_type == 'Triple' else 2 if room_type == 'Studio' else 4
                        current_occupants = random.randint(0, max_occupants)
                        is_accessible = random.choice([0, 1]) if floor == 1 else 0
                        status = 'Occupied' if current_occupants > 0 else random.choice(statuses)
                        monthly_rent = random.randint(400, 1200)

                        cursor.execute('''
                        INSERT INTO housing_rooms
                        (room_id, building_id, room_number, floor_number, room_type, max_occupants, current_occupants,
                        is_accessible, status, monthly_rent, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (room_id, building_id, room_number, floor, room_type, max_occupants, current_occupants,
                             is_accessible, status, monthly_rent, timestamp, timestamp))

            # Create a test application and assignment for student S12345
            application_id = generate_id('APP')
            cursor.execute('''
            INSERT INTO housing_applications
            (application_id, student_id, application_date, preferred_building_id, preferred_room_type,
            requested_move_in_date, requested_duration_months, special_requirements, status,
            created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (application_id, 'S12345', timestamp, 'B001', 'Single',
                 (datetime.datetime.now() + datetime.timedelta(days=30)).strftime('%Y-%m-%d'),
                 9, None, 'Approved', timestamp, timestamp))

            # Find an available room for assignment
            cursor.execute('''
            SELECT room_id, monthly_rent FROM housing_rooms
            WHERE building_id = 'B001' AND room_type = 'Single' AND status = 'Available'
            LIMIT 1
            ''')
            room_data = cursor.fetchone()

            if room_data:
                room_id, monthly_rent = room_data
                assignment_id = generate_id('ASG')
                move_in_date = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime('%Y-%m-%d')
                move_out_date = (datetime.datetime.now() + datetime.timedelta(days=30 + 9*30)).strftime('%Y-%m-%d')
                contract_number = generate_id('CNT')

                cursor.execute('''
                INSERT INTO housing_assignments
                (assignment_id, application_id, student_id, room_id, move_in_date, planned_move_out_date,
                contract_number, monthly_rent, status, assigned_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (assignment_id, application_id, 'S12345', room_id, move_in_date, move_out_date,
                     contract_number, monthly_rent, 'Active', 'system', timestamp, timestamp))

                # Update room status and occupancy
                cursor.execute('''
                UPDATE housing_rooms
                SET current_occupants = current_occupants + 1, status = 'Occupied'
                WHERE room_id = ?
                ''', (room_id,))

                # Create a test maintenance request
                request_id = generate_id('REQ')
                cursor.execute('''
                INSERT INTO housing_maintenance_requests
                (request_id, room_id, student_id, request_date, issue_type, description, priority, status,
                created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (request_id, room_id, 'S12345', timestamp, 'Plumbing',
                     'Leaking faucet in bathroom', 'Medium', 'Open', timestamp, timestamp))

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
