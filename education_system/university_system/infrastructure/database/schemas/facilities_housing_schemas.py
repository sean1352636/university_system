from __future__ import annotations
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.university_system.core.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_facilities_management_system_db():
    """Initialize the Facilities & Space Management database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Facilities & Space Management"))

        # Buildings
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

        # Rooms
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id INTEGER NOT NULL,
            room_number TEXT NOT NULL,
            room_name TEXT,
            floor_number INTEGER,
            room_type TEXT NOT NULL,
            capacity INTEGER,
            area_sqft REAL,
            features TEXT,
            equipment TEXT,
            accessibility_compliant BOOLEAN DEFAULT 1,
            status TEXT DEFAULT 'available',
            FOREIGN KEY (building_id) REFERENCES buildings (building_id)
        )
        ''')

        # Room bookings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS room_bookings (
            booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            booked_by TEXT NOT NULL,
            booking_type TEXT NOT NULL,
            purpose TEXT,
            start_datetime TEXT NOT NULL,
            end_datetime TEXT NOT NULL,
            setup_required TEXT,
            equipment_needed TEXT,
            expected_attendees INTEGER,
            recurrence_pattern TEXT,
            booking_status TEXT DEFAULT 'confirmed',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms (room_id)
        )
        ''')

        # Maintenance requests
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS maintenance_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_type TEXT NOT NULL,
            building_id INTEGER,
            room_id INTEGER,
            request_type TEXT NOT NULL,
            priority TEXT NOT NULL,
            description TEXT NOT NULL,
            reported_by TEXT NOT NULL,
            reported_date TEXT DEFAULT CURRENT_TIMESTAMP,
            assigned_to TEXT,
            assigned_date TEXT,
            scheduled_date TEXT,
            completion_date TEXT,
            status TEXT DEFAULT 'open',
            cost REAL,
            notes TEXT,
            FOREIGN KEY (building_id) REFERENCES buildings (building_id),
            FOREIGN KEY (room_id) REFERENCES rooms (room_id)
        )
        ''')

        # Work orders
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS work_orders (
            work_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            work_order_type TEXT NOT NULL,
            description TEXT NOT NULL,
            assigned_technician TEXT,
            estimated_hours REAL,
            actual_hours REAL,
            materials_cost REAL,
            labor_cost REAL,
            total_cost REAL,
            start_date TEXT,
            completion_date TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (request_id) REFERENCES maintenance_requests (request_id)
        )
        ''')

        # Asset inventory
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS facility_assets (
            asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_name TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            asset_tag TEXT UNIQUE,
            building_id INTEGER,
            room_id INTEGER,
            purchase_date TEXT,
            purchase_cost REAL,
            warranty_expiry TEXT,
            maintenance_schedule TEXT,
            last_maintenance_date TEXT,
            condition TEXT DEFAULT 'good',
            status TEXT DEFAULT 'active',
            FOREIGN KEY (building_id) REFERENCES buildings (building_id),
            FOREIGN KEY (room_id) REFERENCES rooms (room_id)
        )
        ''')

        # Energy usage tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS energy_usage (
            usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id INTEGER NOT NULL,
            usage_type TEXT NOT NULL,
            reading_date TEXT NOT NULL,
            meter_reading REAL NOT NULL,
            consumption REAL,
            cost REAL,
            billing_period_start TEXT,
            billing_period_end TEXT,
            FOREIGN KEY (building_id) REFERENCES buildings (building_id)
        )
        ''')

        # Space utilization analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS space_utilization (
            utilization_id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            measurement_date TEXT NOT NULL,
            occupancy_rate REAL,
            booking_rate REAL,
            peak_usage_time TEXT,
            average_attendees REAL,
            total_booking_hours REAL,
            FOREIGN KEY (room_id) REFERENCES rooms (room_id)
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Facilities & Space Management"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Facilities Management", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# COURSE EVALUATION SYSTEM SCHEMAS
# ============================================================================


def init_housing_tables():
    """Initialize housing system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="housing"))

        # Create accommodation_documents table
        cursor.execute('''
        CREATE TABLE accommodation_documents (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            accommodation_id INTEGER NOT NULL,
                            document_name TEXT NOT NULL,
                            document_path TEXT NOT NULL,
                            uploaded_by TEXT,
                            uploaded_at TEXT,
                            FOREIGN KEY (accommodation_id) REFERENCES accommodations(id)
                        )
        ''')

        # Create accommodation_templates table
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

        # Create accommodation_types table
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

        # Create accommodations table
        cursor.execute('''
        CREATE TABLE accommodations (
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

        # Create chat_room_invitations table
        cursor.execute('''
        CREATE TABLE chat_room_invitations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    invited_by INTEGER NOT NULL,
                    invited_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    responded_at TEXT,
                    FOREIGN KEY (room_id) REFERENCES chat_rooms (id),
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (invited_by) REFERENCES users (id)
                )
        ''')

        # Create chat_room_members table
        cursor.execute('''
        CREATE TABLE chat_room_members (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        room_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        joined_at TEXT NOT NULL,
                        is_admin INTEGER DEFAULT 0,
                        FOREIGN KEY (room_id) REFERENCES chat_rooms (id),
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
        ''')

        # Create chat_rooms table
        cursor.execute('''
        CREATE TABLE chat_rooms (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        room_type TEXT NOT NULL,
                        created_by INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        FOREIGN KEY (created_by) REFERENCES users (id)
                    )
        ''')

        # Create housing_applications table
        cursor.execute('''
        CREATE TABLE housing_applications (
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

        # Create housing_buildings table
        cursor.execute('''
        CREATE TABLE housing_buildings (
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

        # Create housing_inspections table
        cursor.execute('''
        CREATE TABLE housing_inspections (
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

        # Create housing_inventory table
        cursor.execute('''
        CREATE TABLE housing_inventory (
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

        # Create housing_maintenance_requests table
        cursor.execute('''
        CREATE TABLE housing_maintenance_requests (
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

        # Create housing_rooms table
        cursor.execute('''
        CREATE TABLE housing_rooms (
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

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="housing"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="housing", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# INTEGRATION TABLES (6 tables)
# ============================================================================


def init_parking_tables():
    """Initialize parking system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="parking"))

        # Create transportation table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS transportation (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        route_name TEXT,
                        bus_number TEXT,
                        pickup_time TEXT,
                        dropoff_time TEXT,
                        pickup_location TEXT,
                        dropoff_location TEXT,
                        driver_name TEXT,
                        driver_phone TEXT,
                        active BOOLEAN DEFAULT 1,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create parking_lots table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_lots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_name TEXT NOT NULL,
            location TEXT,
            total_spaces INTEGER DEFAULT 0,
            available_spaces INTEGER DEFAULT 0,
            hourly_rate DECIMAL(5,2) DEFAULT 0.00,
            daily_rate DECIMAL(5,2) DEFAULT 0.00,
            monthly_rate DECIMAL(5,2) DEFAULT 0.00,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Create parking_spaces table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_spaces (
            space_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_id INTEGER NOT NULL,
            space_number TEXT NOT NULL,
            space_type TEXT DEFAULT 'standard',
            is_available BOOLEAN DEFAULT 1,
            is_accessible BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lot_id) REFERENCES parking_lots (id)
        )
        ''')

        # Create vehicles table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            license_plate TEXT NOT NULL UNIQUE,
            make TEXT,
            model TEXT,
            year INTEGER,
            color TEXT,
            is_active BOOLEAN DEFAULT 1,
            registered_date TEXT DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Create parking_permits table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_permits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            vehicle_id INTEGER NOT NULL,
            lot_id INTEGER,
            permit_type TEXT DEFAULT 'standard',
            issue_date TEXT DEFAULT CURRENT_TIMESTAMP,
            expiry_date TEXT,
            status TEXT DEFAULT 'active',
            fee_paid DECIMAL(10,2) DEFAULT 0.00,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id),
            FOREIGN KEY (lot_id) REFERENCES parking_lots (id)
        )
        ''')

        # Create parking_violations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER,
            license_plate TEXT,
            lot_id INTEGER,
            space_id INTEGER,
            violation_type TEXT NOT NULL,
            violation_date TEXT DEFAULT CURRENT_TIMESTAMP,
            fine_amount DECIMAL(10,2) DEFAULT 0.00,
            status TEXT DEFAULT 'pending',
            issued_by TEXT,
            paid_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id),
            FOREIGN KEY (lot_id) REFERENCES parking_lots (id),
            FOREIGN KEY (space_id) REFERENCES parking_spaces (space_id)
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="parking"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="parking", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# PEER_SUPPORT TABLES (4 tables)
# ============================================================================


def init_travel_tables():
    """Initialize travel system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="travel"))

        # Create trip_expenses table
        cursor.execute('''
        CREATE TABLE trip_expenses (
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
        CREATE TABLE trip_itinerary (
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

        # Create trip_participants table
        cursor.execute('''
        CREATE TABLE trip_participants (
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
        CREATE TABLE trip_staff (
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

        # Create trips table
        cursor.execute('''
        CREATE TABLE trips (
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

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="travel"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="travel", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# WELLNESS TABLES (3 tables)
# ============================================================================


