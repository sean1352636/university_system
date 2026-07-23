from __future__ import annotations
from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.post_18.university_system.core.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_degree_audit_system_db():
    """Initialize the Degree Audit & Academic Advising System database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Degree Audit & Academic Advising System"))

        # Degree programs/majors
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS degree_programs (
            program_id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_code TEXT NOT NULL UNIQUE,
            program_name TEXT NOT NULL,
            degree_type TEXT NOT NULL,
            department TEXT,
            total_credits_required INTEGER NOT NULL,
            min_gpa_required REAL DEFAULT 2.0,
            max_years_allowed INTEGER DEFAULT 4,
            description TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Program requirements (core courses, electives, etc.)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS degree_requirements (
            requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_id INTEGER NOT NULL,
            requirement_type TEXT NOT NULL,
            requirement_name TEXT NOT NULL,
            description TEXT,
            credits_required INTEGER NOT NULL,
            min_grade TEXT,
            is_mandatory BOOLEAN DEFAULT 1,
            display_order INTEGER DEFAULT 0,
            FOREIGN KEY (program_id) REFERENCES degree_programs (program_id)
        )
        ''')

        # Required courses for each requirement category
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS requirement_courses (
            req_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
            requirement_id INTEGER NOT NULL,
            module_code TEXT NOT NULL,
            is_alternative BOOLEAN DEFAULT 0,
            alternative_group INTEGER,
            FOREIGN KEY (requirement_id) REFERENCES degree_requirements (requirement_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Course prerequisites
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_prerequisites (
            prerequisite_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            prerequisite_module_code TEXT NOT NULL,
            min_grade TEXT,
            is_corequisite BOOLEAN DEFAULT 0,
            FOREIGN KEY (module_code) REFERENCES modules (module_code),
            FOREIGN KEY (prerequisite_module_code) REFERENCES modules (module_code)
        )
        ''')

        # Student degree progress tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_degree_progress (
            progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            program_id INTEGER NOT NULL,
            enrollment_year INTEGER NOT NULL,
            total_credits_earned REAL DEFAULT 0,
            current_gpa REAL DEFAULT 0,
            completion_percentage REAL DEFAULT 0,
            expected_graduation_date TEXT,
            status TEXT DEFAULT 'in_progress',
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (program_id) REFERENCES degree_programs (program_id)
        )
        ''')

        # Requirement completion tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS requirement_completion (
            completion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            requirement_id INTEGER NOT NULL,
            credits_completed REAL DEFAULT 0,
            is_completed BOOLEAN DEFAULT 0,
            completed_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (requirement_id) REFERENCES degree_requirements (requirement_id)
        )
        ''')

        # What-if scenarios for degree planning
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS degree_what_if_scenarios (
            scenario_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            scenario_name TEXT NOT NULL,
            target_program_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (target_program_id) REFERENCES degree_programs (program_id)
        )
        ''')

        # Academic advising appointments
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS advising_appointments (
            appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            advisor_id TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 30,
            appointment_type TEXT NOT NULL,
            status TEXT DEFAULT 'scheduled',
            topic TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Graduation audit checklist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS graduation_checklist (
            checklist_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            program_id INTEGER NOT NULL,
            all_requirements_met BOOLEAN DEFAULT 0,
            gpa_requirement_met BOOLEAN DEFAULT 0,
            credit_requirement_met BOOLEAN DEFAULT 0,
            residency_requirement_met BOOLEAN DEFAULT 0,
            financial_clearance BOOLEAN DEFAULT 0,
            audit_date TEXT DEFAULT CURRENT_DATE,
            graduation_date TEXT,
            conferral_status TEXT DEFAULT 'pending',
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (program_id) REFERENCES degree_programs (program_id)
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Degree Audit & Academic Advising System"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Degree Audit System", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# CAREER SERVICES PLATFORM SCHEMAS
# ============================================================================


