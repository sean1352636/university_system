"""
Database schema initialization for Degree Audit & Academic Advising System
"""

from education_system.university_system.infrastructure.database.db import transaction


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

        # ---- Ceremony scheduling -----------------------------------------
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS graduation_ceremonies (
                ceremony_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ceremony_name TEXT NOT NULL,
                ceremony_date TEXT NOT NULL,
                ceremony_time TEXT NOT NULL,
                venue TEXT NOT NULL,
                capacity INTEGER NOT NULL DEFAULT 200,
                cohort_filter TEXT DEFAULT '',
                rsvp_deadline TEXT,
                guest_tickets_per_graduand INTEGER DEFAULT 2,
                status TEXT DEFAULT 'scheduled',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ceremony_rsvps (
                rsvp_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ceremony_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                rsvp_status TEXT NOT NULL DEFAULT 'pending',
                num_guests INTEGER NOT NULL DEFAULT 0,
                accessibility_notes TEXT DEFAULT '',
                name_pronunciation TEXT DEFAULT '',
                recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (ceremony_id) REFERENCES graduation_ceremonies(ceremony_id) ON DELETE CASCADE,
                UNIQUE(ceremony_id, student_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ceremony_gown_orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ceremony_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                gown_size TEXT DEFAULT '',
                hood_subject TEXT DEFAULT '',
                hat_size TEXT DEFAULT '',
                supplier TEXT DEFAULT '',
                collection_slot TEXT DEFAULT '',
                status TEXT DEFAULT 'ordered',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (ceremony_id) REFERENCES graduation_ceremonies(ceremony_id) ON DELETE CASCADE,
                UNIQUE(ceremony_id, student_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ceremony_seat_assignments (
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ceremony_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                section TEXT DEFAULT 'A',
                row_label TEXT NOT NULL,
                seat_number INTEGER NOT NULL,
                is_accessibility INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                FOREIGN KEY (ceremony_id) REFERENCES graduation_ceremonies(ceremony_id) ON DELETE CASCADE,
                UNIQUE(ceremony_id, student_id),
                UNIQUE(ceremony_id, section, row_label, seat_number)
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ceremony_date ON graduation_ceremonies(ceremony_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rsvp_ceremony ON ceremony_rsvps(ceremony_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gown_ceremony  ON ceremony_gown_orders(ceremony_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_seat_ceremony  ON ceremony_seat_assignments(ceremony_id)')

        # ---- Records & artefacts ----------------------------------------
        # Parchment / certificate print queue. Each row references a record
        # in the shared ``certificates`` table (created on demand by
        # CertificateService) via ``certificate_id`` / ``certificate_number``.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS graduation_print_queue (
                queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ceremony_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                certificate_id INTEGER,
                certificate_number TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                printed_at TEXT,
                dispatched_at TEXT,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (ceremony_id) REFERENCES graduation_ceremonies(ceremony_id) ON DELETE CASCADE,
                UNIQUE(ceremony_id, student_id)
            )
        ''')

        # Frozen transcript snapshot at conferral. ``snapshot_html`` holds the
        # immutable rendered transcript; ``snapshot_hash`` is a SHA-256 so
        # external verifiers can confirm the bytes haven't changed.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transcript_freezes (
                freeze_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                program_id INTEGER,
                academic_year TEXT,
                snapshot_html TEXT NOT NULL,
                snapshot_hash TEXT NOT NULL,
                frozen_at TEXT NOT NULL DEFAULT (datetime('now')),
                frozen_by TEXT,
                gpa TEXT,
                classification TEXT,
                notes TEXT DEFAULT '',
                UNIQUE(student_id, academic_year)
            )
        ''')

        # One-time transcript access tokens issued to employers / verifiers.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transcript_access_tokens (
                token_id INTEGER PRIMARY KEY AUTOINCREMENT,
                freeze_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                requested_by TEXT,
                employer_name TEXT,
                employer_email TEXT,
                purpose TEXT DEFAULT '',
                issued_at TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at TEXT,
                accessed_at TEXT,
                revoked INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (freeze_id) REFERENCES transcript_freezes(freeze_id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_print_queue_ceremony ON graduation_print_queue(ceremony_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_freeze_student ON transcript_freezes(student_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_token_freeze   ON transcript_access_tokens(freeze_id)')

        print("✅ Degree Audit database schema initialized successfully")


__all__ = ['initialize_degree_audit_database']
