#!/usr/bin/env python3
"""
Unified Database Setup Script
Creates a single comprehensive student_records.db file with all necessary tables
"""
from education_system.university_system.infrastructure.database.db import sqlite3
import os
import shutil
from datetime import datetime
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH, DB_DIR
from education_system.university_system.modules.shared.utils.i18n import get_text

def backup_existing_database():
    """Backup the existing student_records.db"""
    original_path = DEFAULT_DB_PATH
    backup_path = DB_DIR / f"student_records_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

    if original_path.exists():
        shutil.copy2(str(original_path), str(backup_path))
        print(get_text("setup.unified_database.backup_success", path=backup_path))
        return backup_path
    return None

def create_unified_database():
    """Create the unified student_records.db with all tables"""
    db_path = str(DEFAULT_DB_PATH)

    print(get_text("setup.unified_database.creating", path=db_path))

    # Remove existing file if it exists
    if DEFAULT_DB_PATH.exists():
        DEFAULT_DB_PATH.unlink()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(get_text("setup.unified_database.creating_schema"))

    # ==================== CORE STUDENT TABLES ====================

    # Students table (core student information)
    cursor.execute('''
    CREATE TABLE students (
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

    # Users table (system users including students, staff, admin)
    cursor.execute('''
    CREATE TABLE users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        email TEXT,
        first_name TEXT,
        last_name TEXT,
        role TEXT DEFAULT 'student',
        student_id TEXT,
        is_active BOOLEAN DEFAULT 1,
        last_login TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )
    ''')

    # ==================== ACADEMIC TABLES ====================

    # Modules/Courses
    cursor.execute('''
    CREATE TABLE modules (
        module_code TEXT PRIMARY KEY,
        module_name TEXT,
        module_type TEXT
    )
    ''')

    # Student module enrollments
    cursor.execute('''
    CREATE TABLE student_modules (
        enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        module_id TEXT NOT NULL,
        enrollment_date TEXT,
        status TEXT DEFAULT 'enrolled',
        grade TEXT,
        credits_earned INTEGER DEFAULT 0,
        semester TEXT,
        year TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (module_id) REFERENCES modules (module_id)
    )
    ''')

    # Student grades
    cursor.execute('''
    CREATE TABLE student_grades (
        grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        module_id TEXT NOT NULL,
        assessment_type TEXT,
        grade_value TEXT,
        percentage DECIMAL(5,2),
        weight DECIMAL(5,2),
        assessment_date TEXT,
        instructor TEXT,
        comments TEXT,
        is_final BOOLEAN DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (module_id) REFERENCES modules (module_id)
    )
    ''')

    # Attendance tracking
    cursor.execute('''
    CREATE TABLE attendance (
        attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        module_id TEXT NOT NULL,
        class_date TEXT NOT NULL,
        status TEXT DEFAULT 'present',
        arrival_time TEXT,
        departure_time TEXT,
        notes TEXT,
        recorded_by TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (module_id) REFERENCES modules (module_id)
    )
    ''')

    # ==================== FINANCIAL TABLES ====================

    # Fee types
    cursor.execute('''
    CREATE TABLE fee_types (
        fee_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
        fee_name TEXT NOT NULL,
        description TEXT,
        is_recurring BOOLEAN DEFAULT 0,
        academic_year TEXT,
        is_late_fee BOOLEAN DEFAULT 0,
        late_fee_calculation TEXT,
        late_fee_amount DECIMAL(10,2),
        grace_period_days INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Program fees (fees by course/program)
    cursor.execute('''
    CREATE TABLE program_fees (
        program_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
        fee_type_id INTEGER,
        course TEXT NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        currency TEXT DEFAULT 'GBP',
        academic_year TEXT,
        due_date TEXT,
        early_payment_discount DECIMAL(5,2) DEFAULT 0,
        early_payment_days INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (fee_type_id) REFERENCES fee_types (fee_type_id)
    )
    ''')

    # Student fees (individual student fee records)
    cursor.execute('''
    CREATE TABLE student_fees (
        student_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        fee_type_id INTEGER NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        currency TEXT DEFAULT 'GBP',
        status TEXT DEFAULT 'unpaid',
        due_date TEXT,
        last_reminder_sent TEXT,
        reminder_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (fee_type_id) REFERENCES fee_types (fee_type_id)
    )
    ''')

    # Payments
    cursor.execute('''
    CREATE TABLE payments (
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
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        fraud_score DECIMAL(3,2),
        is_suspicious BOOLEAN DEFAULT 0,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )
    ''')

    # Payment allocations (which payment covers which fee)
    cursor.execute('''
    CREATE TABLE payment_allocations (
        allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_id INTEGER NOT NULL,
        student_fee_id INTEGER NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (payment_id) REFERENCES payments (payment_id),
        FOREIGN KEY (student_fee_id) REFERENCES student_fees (student_fee_id)
    )
    ''')

    # Financial alerts
    cursor.execute('''
    CREATE TABLE financial_alerts (
        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_type TEXT NOT NULL,
        priority TEXT DEFAULT 'medium',
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        student_id TEXT,
        amount DECIMAL(10,2),
        currency TEXT DEFAULT 'GBP',
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        acknowledged_at TEXT,
        resolved_at TEXT,
        acknowledged_by TEXT,
        resolved_by TEXT,
        metadata TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )
    ''')

    # Scholarships
    cursor.execute('''
    CREATE TABLE scholarships (
        scholarship_id INTEGER PRIMARY KEY AUTOINCREMENT,
        scholarship_name TEXT NOT NULL,
        description TEXT,
        amount DECIMAL(10,2),
        academic_year TEXT,
        criteria TEXT,
        deadline TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Student scholarships (awarded scholarships)
    cursor.execute('''
    CREATE TABLE student_scholarships (
        student_scholarship_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        scholarship_id INTEGER NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        status TEXT DEFAULT 'active',
        awarded_date TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (scholarship_id) REFERENCES scholarships (scholarship_id)
    )
    ''')

    # ==================== DOCUMENT MANAGEMENT TABLES ====================

    # Document types
    cursor.execute('''
    CREATE TABLE document_types (
        type_id INTEGER PRIMARY KEY AUTOINCREMENT,
        type_name TEXT NOT NULL UNIQUE,
        description TEXT,
        is_required BOOLEAN DEFAULT 0,
        max_file_size INTEGER DEFAULT 10485760,
        allowed_extensions TEXT DEFAULT '.pdf,.jpg,.jpeg,.png,.doc,.docx',
        retention_days INTEGER DEFAULT 2555,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Documents (unified)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS documents (
        document_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_type TEXT NOT NULL DEFAULT 'general',
        source_document_id INTEGER,
        owner_id TEXT,
        owner_type TEXT,
        reference_type TEXT,
        reference_id TEXT,
        document_type TEXT,
        document_name TEXT,
        file_path TEXT,
        file_content TEXT,
        file_size INTEGER,
        file_hash TEXT,
        original_filename TEXT,
        upload_date TEXT,
        expiry_date TEXT,
        issue_date TEXT,
        status TEXT DEFAULT 'active',
        verification_status TEXT,
        verification_date TEXT,
        verification_notes TEXT,
        verified_by TEXT,
        version_number INTEGER DEFAULT 1,
        parent_document_id INTEGER,
        is_current_version INTEGER DEFAULT 1,
        workflow_status TEXT,
        priority INTEGER,
        tags TEXT,
        notes TEXT,
        uploaded_by TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT
    )
    ''')

    # ==================== PARKING SYSTEM TABLES ====================

    # Parking lots
    cursor.execute('''
    CREATE TABLE parking_lots (
        lot_id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    # Parking spaces
    cursor.execute('''
    CREATE TABLE parking_spaces (
        space_id INTEGER PRIMARY KEY AUTOINCREMENT,
        lot_id INTEGER NOT NULL,
        space_number TEXT NOT NULL,
        space_type TEXT DEFAULT 'standard',
        is_available BOOLEAN DEFAULT 1,
        is_accessible BOOLEAN DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lot_id) REFERENCES parking_lots (lot_id)
    )
    ''')

    # Vehicles
    cursor.execute('''
    CREATE TABLE vehicles (
        vehicle_id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    # Parking permits
    cursor.execute('''
    CREATE TABLE parking_permits (
        permit_id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        FOREIGN KEY (vehicle_id) REFERENCES vehicles (vehicle_id),
        FOREIGN KEY (lot_id) REFERENCES parking_lots (lot_id)
    )
    ''')

    # Parking violations
    cursor.execute('''
    CREATE TABLE parking_violations (
        violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        FOREIGN KEY (vehicle_id) REFERENCES vehicles (vehicle_id),
        FOREIGN KEY (lot_id) REFERENCES parking_lots (lot_id),
        FOREIGN KEY (space_id) REFERENCES parking_spaces (space_id)
    )
    ''')

    # ==================== RESTAURANT/COMMERCE TABLES ====================

    # Menu items
    cursor.execute('''
    CREATE TABLE menu_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        category TEXT NOT NULL,
        available BOOLEAN DEFAULT 1,
        ingredients TEXT,
        allergens TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Restaurant orders - now uses unified 'orders' table with source_type='restaurant'
    # The 'orders' table should already exist or be created with source_type column
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id TEXT NOT NULL,
        items TEXT NOT NULL,
        total_amount REAL,
        source_type TEXT DEFAULT 'restaurant',
        order_status TEXT DEFAULT 'pending',
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        delivery_address TEXT,
        special_instructions TEXT,
        payment_method TEXT,
        completed_at TIMESTAMP
    )
    ''')

    # Restaurant inventory
    cursor.execute('''
    CREATE TABLE inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit TEXT NOT NULL,
        minimum_threshold INTEGER DEFAULT 10,
        supplier TEXT,
        cost_per_unit REAL,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Restaurant staff schedules
    cursor.execute('''
    CREATE TABLE staff_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id TEXT NOT NULL,
        shift_date DATE NOT NULL,
        start_time TIME NOT NULL,
        end_time TIME NOT NULL,
        position TEXT NOT NULL,
        status TEXT DEFAULT 'scheduled',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Restaurant suppliers
    cursor.execute('''
    CREATE TABLE restaurant_suppliers (
        supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact_person TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        category TEXT,
        status TEXT DEFAULT 'Active',
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Purchase orders
    cursor.execute('''
    CREATE TABLE purchase_orders (
        po_id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_number TEXT UNIQUE NOT NULL,
        supplier_id INTEGER,
        order_date DATE NOT NULL,
        expected_delivery DATE,
        actual_delivery DATE,
        status TEXT DEFAULT 'Pending',
        total_amount DECIMAL(10,2) NOT NULL,
        tax_amount DECIMAL(10,2) DEFAULT 0,
        shipping_cost DECIMAL(10,2) DEFAULT 0,
        ordered_by TEXT,
        received_by TEXT,
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (supplier_id) REFERENCES restaurant_suppliers (supplier_id)
    )
    ''')

    # Restaurant customers
    cursor.execute('''
    CREATE TABLE restaurant_customers (
        customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        loyalty_points INTEGER DEFAULT 0,
        total_spent REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # ==================== SYSTEM TABLES ====================

    # System logs
    cursor.execute('''
    CREATE TABLE logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        table_name TEXT,
        record_id TEXT,
        old_values TEXT,
        new_values TEXT,
        ip_address TEXT,
        user_agent TEXT,
        session_id TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')

    # System alerts
    cursor.execute('''
    CREATE TABLE alerts (
        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_type TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        priority TEXT DEFAULT 'medium',
        target_user_id INTEGER,
        target_user_type TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        read_at TEXT,
        dismissed_at TEXT,
        expires_at TEXT,
        FOREIGN KEY (target_user_id) REFERENCES users (user_id)
    )
    ''')

    # Saved searches
    cursor.execute('''
    CREATE TABLE saved_searches (
        search_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        search_name TEXT NOT NULL,
        search_type TEXT,
        search_criteria TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_used TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')

    # Trip calendar events (if needed)
    cursor.execute('''
    CREATE TABLE trip_calendar_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        start_date TEXT,
        end_date TEXT,
        location TEXT,
        organizer TEXT,
        participants TEXT,
        status TEXT DEFAULT 'planned',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    print(get_text("setup.unified_database.tables_created"))

    # Add some initial data
    add_initial_data(cursor)

    conn.commit()
    conn.close()

    print(get_text("setup.unified_database.database_created", path=db_path))
    return db_path

def add_initial_data(cursor):
    """Add essential initial data to the database"""
    print(get_text("setup.unified_database.adding_initial_data"))

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    today = datetime.now().strftime('%Y-%m-%d')

    # Sample students (13 columns: student_id, email_address, title, first_name, middle_name, last_name, gender, dob, age, course, registration_datetime, status, enrollment_date)
    students = [
        ('STU001', 'john.smith@university.ac.uk', 'Mr', 'John', '', 'Smith', 'male', '2002-05-15', 22, 'Computer Science', now, 'Active', '2024-09-01'),
        ('STU002', 'sarah.johnson@university.ac.uk', 'Ms', 'Sarah', '', 'Johnson', 'female', '2003-08-22', 21, 'Business Administration', now, 'Active', '2024-09-01'),
        ('STU003', 'michael.brown@university.ac.uk', 'Mr', 'Michael', '', 'Brown', 'male', '2001-12-10', 23, 'Engineering', now, 'Active', '2024-09-01'),
        ('STU004', 'emma.davis@university.ac.uk', 'Ms', 'Emma', '', 'Davis', 'female', '2002-03-18', 22, 'Psychology', now, 'Active', '2024-09-01'),
        ('STU005', 'james.wilson@university.ac.uk', 'Mr', 'James', '', 'Wilson', 'male', '2003-11-05', 21, 'Mathematics', now, 'Active', '2024-09-01')
    ]

    cursor.executemany('''
    INSERT INTO students
    (student_id, email_address, title, first_name, middle_name, last_name, gender, dob, age, course, registration_datetime, status, enrollment_date)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', students)

    # Sample users
    users = [
        ('admin', 'admin_password_hash', 'admin@university.ac.uk', 'System', 'Administrator', 'admin', None, 1, None, now, now),
        ('jsmith', 'student_password_hash', 'john.smith@university.ac.uk', 'John', 'Smith', 'student', 'STU001', 1, None, now, now),
        ('sjohnson', 'student_password_hash', 'sarah.johnson@university.ac.uk', 'Sarah', 'Johnson', 'student', 'STU002', 1, None, now, now)
    ]

    cursor.executemany('''
    INSERT INTO users
    (username, password_hash, email, first_name, last_name, role, student_id, is_active, last_login, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', users)

    # Fee types
    fee_types = [
        ('Tuition Fee', 'Annual tuition payment', 0, '2024-2025', 0, None, None, 0, now, now),
        ('Registration Fee', 'One-time registration fee', 0, '2024-2025', 0, None, None, 0, now, now),
        ('Library Fee', 'Annual library access fee', 1, '2024-2025', 0, None, None, 0, now, now),
        ('Lab Fee', 'Laboratory access and materials', 1, '2024-2025', 0, None, None, 0, now, now),
        ('Late Payment Fee', 'Fee for overdue payments', 0, '2024-2025', 1, 'fixed', 50.00, 7, now, now)
    ]

    cursor.executemany('''
    INSERT INTO fee_types
    (fee_name, description, is_recurring, academic_year, is_late_fee,
     late_fee_calculation, late_fee_amount, grace_period_days, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', fee_types)

    # Sample financial alerts
    financial_alerts = [
        ('payment_overdue', 'high', 'Overdue Payment Alert', 'Student STU003 has overdue payment of £150.00', 'STU003', 150.00, 'GBP', 'active', now, None, None, None, None, None),
        ('high_risk_student', 'medium', 'High Risk Student', 'Student flagged for payment risk assessment', 'STU002', None, 'GBP', 'active', now, None, None, None, None, None),
        ('low_balance', 'low', 'Low Account Balance', 'System account balance below threshold', None, 500.00, 'GBP', 'active', now, None, None, None, None, None)
    ]

    cursor.executemany('''
    INSERT INTO financial_alerts
    (alert_type, priority, title, message, student_id, amount, currency, status,
     created_at, acknowledged_at, resolved_at, acknowledged_by, resolved_by, metadata)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', financial_alerts)

    # Document types
    document_types = [
        ('Transcript', 'Official academic transcript', 1, 10485760, '.pdf,.jpg,.png', 7300, now, now),
        ('ID Card', 'Student identification document', 1, 5242880, '.jpg,.jpeg,.png', 1825, now, now),
        ('Medical Certificate', 'Medical fitness certificate', 0, 10485760, '.pdf,.jpg,.png', 365, now, now),
        ('Passport', 'Passport copy for international students', 0, 10485760, '.pdf,.jpg,.png', 3650, now, now)
    ]

    cursor.executemany('''
    INSERT INTO document_types
    (type_name, description, is_required, max_file_size, allowed_extensions, retention_days, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', document_types)

    # Sample modules (3 columns: module_code, module_name, module_type)
    modules = [
        ('CS101', 'Introduction to Programming', 'Core'),
        ('MATH201', 'Calculus I', 'Core'),
        ('ENG301', 'Advanced Engineering', 'Elective')
    ]

    cursor.executemany('''
    INSERT INTO modules
    (module_code, module_name, module_type)
    VALUES (?, ?, ?)
    ''', modules)

    print(get_text("setup.unified_database.initial_data_added"))


def seed_default_staff(db_path=None):
    """Seed default staff profiles into the staff_profiles table (university)."""
    path = str(db_path or DEFAULT_DB_PATH)
    conn = sqlite3.connect(path)
    try:
        cursor = conn.cursor()
        staff_profiles = [
            ("staff", "STF0001", "Computer Science", "Professor of Computer Science",
             "full-time", "2015-09-01", None, None, "Room 4.12, CS Building", "4012",
             "Alan Turing", "01onal-000001", "Spouse",
             "Leading researcher in artificial intelligence and machine learning.",
             "AI, Machine Learning, Data Science",
             "PhD Computer Science (Imperial), MSc AI (Edinburgh)"),
            ("slecturer", "STF0002", "Mathematics", "Senior Lecturer",
             "full-time", "2018-01-15", None, None, "Room 2.05, Maths Building", "2005",
             "Grace Hopper", "01onal-000002", "Partner",
             "Specialist in applied mathematics and statistics.",
             "Statistics, Applied Mathematics, Numerical Methods",
             "PhD Mathematics (Oxford), BSc Mathematics (Durham)"),
            ("rfellow", "STF0003", "Engineering", "Research Fellow",
             "full-time", "2021-06-01", None, None, "Lab 3.08, Engineering Block", "3008",
             "Marie Curie", "01onal-000003", "Sister",
             "Postdoctoral researcher in renewable energy systems.",
             "Renewable Energy, Thermodynamics, Sustainability",
             "PhD Mechanical Engineering (Manchester), MEng (Leeds)"),
            ("labtech", "STF0004", "Computer Science", "Lab Technician",
             "full-time", "2019-03-10", None, "STF0001",
             "Lab G.01, CS Building", "4001",
             "Charles Babbage", "01onal-000004", "Brother",
             "Responsible for maintaining computer labs and equipment.",
             "Hardware, Networking, Linux Administration",
             "BSc Computer Networks (Liverpool John Moores)"),
            ("acadvisor", "STF0005", "Student Services", "Academic Advisor",
             "full-time", "2020-09-01", None, None, "Room 1.03, Student Hub", "1003",
             "Florence Nightingale", "01onal-000005", "Mother",
             "Providing academic guidance and pastoral support to students.",
             "Student Welfare, Academic Planning, Career Guidance",
             "MA Education (UCL), PGCE (Cambridge)"),
        ]
        for (uid, eid, dept, title, etype, hire, contract_end, mgr, office,
             ext, ec_name, ec_phone, ec_rel, bio, expertise, quals) in staff_profiles:
            cursor.execute(
                """INSERT OR IGNORE INTO staff_profiles
                   (user_id, employee_id, department, job_title, employment_type,
                    hire_date, contract_end_date, manager_id, office_location,
                    phone_extension, emergency_contact_name, emergency_contact_phone,
                    emergency_contact_relationship, bio, expertise_areas, qualifications)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (uid, eid, dept, title, etype, hire, contract_end, mgr, office,
                 ext, ec_name, ec_phone, ec_rel, bio, expertise, quals),
            )
        conn.commit()
    finally:
        conn.close()


def migrate_existing_data():
    """Migrate data from existing databases if they exist"""
    print("🔄 Migrating existing data...")

    # This is a basic migration - in a real scenario you might want more sophisticated logic
    existing_db = DEFAULT_DB_PATH
    if os.path.exists(existing_db):
        print(f"Found existing database: {existing_db}")
        # For now, we'll just note this - the new database has sample data
        # In production, you'd want to copy over the real data
        print("ℹ️  Using sample data for now. Real migration would copy existing records.")

def update_database_connections():
    """Update database connection code to use the unified database"""
    print(f"🔧 Database connections should be updated to use: {DEFAULT_DB_PATH}")
    print("   Update your get_connection() function to point to the new location.")

def test_unified_database():
    """Test the unified database"""
    print("🧪 Testing unified database...")

    db_path = str(DEFAULT_DB_PATH)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Test basic queries
        cursor.execute("SELECT COUNT(*) FROM students")
        student_count = cursor.fetchone()[0]
        print(f"✅ Students table: {student_count} records")

        cursor.execute("SELECT COUNT(*) FROM financial_alerts")
        alert_count = cursor.fetchone()[0]
        print(f"✅ Financial alerts table: {alert_count} records")

        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"✅ Users table: {user_count} records")

        # Test joins
        cursor.execute('''
        SELECT s.first_name, s.last_name, s.course, COUNT(fa.alert_id) as alert_count
        FROM students s
        LEFT JOIN financial_alerts fa ON s.student_id = fa.student_id
        GROUP BY s.student_id
        ''')
        results = cursor.fetchall()
        print(f"✅ Join test: Retrieved {len(results)} student-alert combinations")

        # List all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"✅ Total tables in unified database: {len(tables)}")
        print(f"   Tables: {', '.join(tables)}")

        conn.close()
        print("🎉 Database test completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def main():
    """Main function to set up the unified database"""
    print("🚀 Setting up unified student_records.db database")
    print("=" * 60)

    try:
        # Step 1: Backup existing database
        backup_path = backup_existing_database()

        # Step 2: Create unified database
        db_path = create_unified_database()

        # Step 3: Migrate existing data (placeholder for now)
        migrate_existing_data()

        # Step 4: Test the database
        if test_unified_database():
            print("\n🎉 SUCCESS! Unified database setup completed!")
            print(f"📁 Your new database is at: {os.path.abspath(db_path)}")
            print("\n📋 Next steps:")
            print("1. Update your database connection code to use: ./student_records.db")
            print("2. Test your applications with the new database")
            if backup_path:
                print(f"3. Your original database is backed up at: {backup_path}")
        else:
            print("\n❌ Database setup completed but tests failed. Please check the database.")

    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()