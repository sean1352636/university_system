from tkinter import messagebox

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core import paths

try:
    from education_system.post_18.university_system.modules.domain.health.services.health_portal import init_enhanced_health_db
except ImportError:
    init_enhanced_health_db = None


class DatabaseMixin:
    """Mixin for database schema initialization."""

    def init_database(self):
        """Initialize the database with all required tables"""
        try:
            if init_enhanced_health_db:
                try:
                    import education_system.post_18.university_system.infrastructure.database.db as _db_module
                    _old_db_path = getattr(_db_module, 'DEFAULT_DB_PATH', None)
                    _db_module.DEFAULT_DB_PATH = str(paths.DEFAULT_DB_PATH)
                    init_enhanced_health_db()
                    if _old_db_path is not None:
                        _db_module.DEFAULT_DB_PATH = _old_db_path
                except Exception as e:
                    print(f"Warning: failed to initialize enhanced health DB: {e}")

            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    first_name TEXT,
                    last_name TEXT,
                    age INTEGER,
                    gender TEXT,
                    email TEXT,
                    phone TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS health_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    record_type TEXT,
                    record_date TEXT,
                    description TEXT,
                    provider TEXT,
                    confidential INTEGER DEFAULT 0,
                    created_at TEXT,
                    encrypted_data TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vaccination_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    vaccine_name TEXT,
                    administered_date TEXT,
                    expiry_date TEXT,
                    lot_number TEXT,
                    manufacturer TEXT,
                    administered_by TEXT,
                    location TEXT,
                    adverse_reaction INTEGER DEFAULT 0,
                    reaction_description TEXT,
                    verified INTEGER DEFAULT 0,
                    verified_by TEXT,
                    verified_date TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS health_appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    appointment_type TEXT,
                    appointment_date TEXT,
                    appointment_time TEXT,
                    provider TEXT,
                    reason TEXT,
                    status TEXT DEFAULT 'scheduled',
                    notes TEXT,
                    scheduled_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS allergies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    allergen TEXT,
                    severity TEXT,
                    reaction_description TEXT,
                    diagnosed_date TEXT,
                    provider TEXT,
                    verified INTEGER DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS prescriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    medication_name TEXT,
                    dosage TEXT,
                    frequency TEXT,
                    prescribed_date TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    prescriber TEXT,
                    pharmacy TEXT,
                    status TEXT DEFAULT 'active',
                    notes TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vital_signs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    measurement_date TEXT,
                    blood_pressure_systolic INTEGER,
                    blood_pressure_diastolic INTEGER,
                    heart_rate INTEGER,
                    temperature REAL,
                    weight REAL,
                    height REAL,
                    bmi REAL,
                    recorded_by TEXT,
                    notes TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_trail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    action TEXT,
                    resource_type TEXT,
                    resource_id TEXT,
                    old_values TEXT,
                    new_values TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    timestamp TEXT,
                    session_id TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS medical_conditions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    condition_name TEXT,
                    icd_code TEXT,
                    severity TEXT,
                    diagnosed_date TEXT,
                    status TEXT DEFAULT 'active',
                    provider TEXT,
                    notes TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS care_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    condition_id INTEGER,
                    plan_name TEXT,
                    description TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    provider TEXT,
                    status TEXT DEFAULT 'active',
                    goals TEXT,
                    interventions TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (condition_id) REFERENCES medical_conditions (id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    referring_provider TEXT,
                    specialist_provider TEXT,
                    specialty TEXT,
                    reason TEXT,
                    urgency TEXT,
                    referral_date TEXT,
                    appointment_date TEXT,
                    status TEXT DEFAULT 'pending',
                    notes TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS health_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    metric_value REAL,
                    measurement_date TEXT,
                    category TEXT,
                    subcategory TEXT,
                    metadata TEXT,
                    calculated_at TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS screening_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    screening_type TEXT,
                    due_date TEXT,
                    completed_date TEXT,
                    status TEXT DEFAULT 'due',
                    provider TEXT,
                    results TEXT,
                    next_due_date TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS risk_assessments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    assessment_type TEXT,
                    risk_score INTEGER,
                    risk_factors TEXT,
                    recommendations TEXT,
                    assessed_date TEXT,
                    assessed_by TEXT,
                    follow_up_date TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS emergency_contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    contact_name TEXT,
                    relationship TEXT,
                    phone_primary TEXT,
                    phone_secondary TEXT,
                    email TEXT,
                    address TEXT,
                    priority_order INTEGER,
                    medical_decision_maker INTEGER DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS provider_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_name TEXT,
                    day_of_week INTEGER,
                    start_time TEXT,
                    end_time TEXT,
                    max_appointments INTEGER DEFAULT 10,
                    specialty TEXT,
                    location TEXT,
                    active INTEGER DEFAULT 1,
                    created_at TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS health_campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_name TEXT,
                    campaign_type TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    target_population TEXT,
                    description TEXT,
                    goals TEXT,
                    status TEXT DEFAULT 'planned',
                    budget REAL,
                    created_by TEXT,
                    created_at TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wellness_participation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    program_name TEXT,
                    enrollment_date TEXT,
                    completion_date TEXT,
                    status TEXT DEFAULT 'enrolled',
                    progress_score INTEGER DEFAULT 0,
                    goals_met INTEGER DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS disease_surveillance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    disease_name TEXT,
                    case_date TEXT,
                    student_id TEXT,
                    symptoms TEXT,
                    severity TEXT,
                    status TEXT DEFAULT 'under_investigation',
                    contact_tracing_needed INTEGER DEFAULT 0,
                    contact_tracing_completed INTEGER DEFAULT 0,
                    contacts_identified INTEGER DEFAULT 0,
                    reported_to_health_dept INTEGER DEFAULT 0,
                    isolation_required INTEGER DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS lab_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    test_name TEXT,
                    test_code TEXT,
                    result_value TEXT,
                    reference_range TEXT,
                    units TEXT,
                    status TEXT,
                    ordered_date TEXT,
                    collected_date TEXT,
                    resulted_date TEXT,
                    ordering_provider TEXT,
                    lab_name TEXT,
                    abnormal_flag TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS quality_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    metric_category TEXT,
                    target_value REAL,
                    actual_value REAL,
                    measurement_period TEXT,
                    measured_date TEXT,
                    status TEXT,
                    improvement_needed INTEGER DEFAULT 0,
                    created_at TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS data_retention_policies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_type TEXT,
                    retention_period_days INTEGER,
                    auto_archive INTEGER DEFAULT 0,
                    auto_delete INTEGER DEFAULT 0,
                    created_at TEXT,
                    retention_period_months INTEGER,
                    deletion_method TEXT DEFAULT 'soft',
                    last_cleanup_date TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    updated_at TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS security_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_name TEXT UNIQUE,
                    setting_value TEXT,
                    updated_at TEXT,
                    updated_by TEXT
                )
            ''')

            conn.commit()
            conn.close()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error initializing database: {e}")
