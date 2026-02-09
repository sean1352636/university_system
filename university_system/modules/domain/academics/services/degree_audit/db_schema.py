"""
Database schema initialization for Degree Audit & Academic Advising System
"""

from university_system.infrastructure.database.db import transaction


def initialize_degree_audit_database():
    """Initialize all database tables for the Degree Audit System"""

    with transaction() as conn:
        cursor = conn.cursor()

        # Enable foreign keys
        cursor.execute('PRAGMA foreign_keys = OFF')

        # Degree Programs Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS degree_programs (
                program_id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_code TEXT UNIQUE NOT NULL,
                program_name TEXT NOT NULL,
                degree_type TEXT NOT NULL,
                department TEXT,
                total_credits_required INTEGER NOT NULL,
                min_gpa_required REAL DEFAULT 2.0,
                max_years_allowed INTEGER DEFAULT 4,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

        # Degree Requirements Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS degree_requirements (
                requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_id INTEGER NOT NULL,
                requirement_type TEXT NOT NULL,
                requirement_name TEXT NOT NULL,
                credits_required INTEGER NOT NULL,
                description TEXT,
                min_grade TEXT,
                is_mandatory INTEGER DEFAULT 1,
                display_order INTEGER DEFAULT 0,
                FOREIGN KEY (program_id) REFERENCES degree_programs(program_id) ON DELETE CASCADE
            )
        ''')

        # Required Courses for Requirements
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS requirement_courses (
                req_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                requirement_id INTEGER NOT NULL,
                module_code TEXT NOT NULL,
                is_alternative INTEGER DEFAULT 0,
                alternative_group INTEGER,
                FOREIGN KEY (requirement_id) REFERENCES degree_requirements(requirement_id) ON DELETE CASCADE
            )
        ''')

        # Course Prerequisites Table (for degree audit)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS degree_course_prerequisites (
                prerequisite_id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT NOT NULL,
                prerequisite_module_code TEXT NOT NULL,
                min_grade TEXT,
                is_corequisite INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(module_code, prerequisite_module_code)
            )
        ''')

        # Student Degree Progress Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_degree_progress (
                progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                program_id INTEGER NOT NULL,
                enrollment_year INTEGER NOT NULL,
                total_credits_earned INTEGER DEFAULT 0,
                current_gpa REAL DEFAULT 0.0,
                completion_percentage REAL DEFAULT 0.0,
                expected_graduation_date TEXT,
                last_updated TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (program_id) REFERENCES degree_programs(program_id),
                UNIQUE(student_id, program_id)
            )
        ''')

        # Requirement Completion Tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS requirement_completion (
                completion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                requirement_id INTEGER NOT NULL,
                is_completed INTEGER DEFAULT 0,
                credits_earned INTEGER DEFAULT 0,
                completed_date TEXT,
                FOREIGN KEY (requirement_id) REFERENCES degree_requirements(requirement_id) ON DELETE CASCADE
            )
        ''')

        # What-If Scenarios Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS degree_what_if_scenarios (
                scenario_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                scenario_name TEXT NOT NULL,
                target_program_id INTEGER NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (target_program_id) REFERENCES degree_programs(program_id)
            )
        ''')

        # Advising Appointments Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS advising_appointments (
                appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                advisor_id TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                duration_minutes INTEGER DEFAULT 30,
                appointment_type TEXT NOT NULL,
                topic TEXT,
                notes TEXT,
                status TEXT DEFAULT 'scheduled',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

        # Graduation Checklist Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS graduation_checklist (
                checklist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                program_id INTEGER NOT NULL,
                all_requirements_met INTEGER DEFAULT 0,
                gpa_requirement_met INTEGER DEFAULT 0,
                credit_requirement_met INTEGER DEFAULT 0,
                residency_requirement_met INTEGER DEFAULT 0,
                financial_clearance INTEGER DEFAULT 0,
                conferral_status TEXT DEFAULT 'pending',
                graduation_date TEXT,
                last_checked TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (program_id) REFERENCES degree_programs(program_id),
                UNIQUE(student_id, program_id)
            )
        ''')

        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_student_progress
            ON student_degree_progress(student_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_appointments
            ON advising_appointments(student_id, appointment_date)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_degree_prerequisites
            ON degree_course_prerequisites(module_code)
        ''')

        print("✅ Degree Audit database schema initialized successfully")


__all__ = ['initialize_degree_audit_database']
