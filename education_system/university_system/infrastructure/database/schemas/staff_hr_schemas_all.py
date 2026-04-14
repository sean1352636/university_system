"""
Staff HR Management Database Schemas - Consolidated

All staff HR schema definitions in a single file.
Consolidates the original staff_hr_schemas.py and v2-v7 files.

Sections:
  - Base schemas (Leave, Time & Attendance, Training, Appraisals, Onboarding)
  - V2 schemas (Profiles, Teaching, Admin, Communication, Recruitment)
  - V3 schemas (Asset/Equipment Tracking)
  - V4 schemas (Contracts, Expenses, Grievances, Disciplinary, Exit)
  - V5 schemas (Payroll, Faculty Schedules, Curriculum, Travel, Sabbaticals)
  - V6 schemas (Committees, IP, Lab Booking, Cover, Workload, Directory)
  - V7 schemas (Mentoring, Grant Budgets, Peer Review, Comm Hub, Teaching Load)
"""

from __future__ import annotations

from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.sql_safety import safe_alter_table_add_column


# ======================================================================
# Base schemas (Leave, Time & Attendance, Training, Appraisals, Onboarding)
# ======================================================================

def init_staff_hr_schemas():
    """Initialize all Staff HR Management tables."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # ==================== LEAVE MANAGEMENT ====================

            # Leave Types Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leave_types (
                    leave_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    max_days_per_year INTEGER DEFAULT 0,
                    requires_approval BOOLEAN DEFAULT 1,
                    is_paid BOOLEAN DEFAULT 1,
                    color_code TEXT DEFAULT '#3498db',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Leave Requests Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leave_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    leave_type_id INTEGER NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    total_days REAL NOT NULL,
                    reason TEXT,
                    document_path TEXT,
                    status TEXT DEFAULT 'pending',
                    approved_by TEXT,
                    approved_date TEXT,
                    rejection_reason TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (leave_type_id) REFERENCES leave_types(leave_type_id)
                )
            ''')

            # Leave Balances Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leave_balances (
                    balance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    leave_type_id INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    allocated_days REAL DEFAULT 0,
                    used_days REAL DEFAULT 0,
                    carried_over REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, leave_type_id, year),
                    FOREIGN KEY (leave_type_id) REFERENCES leave_types(leave_type_id)
                )
            ''')

            # ==================== TIME & ATTENDANCE ====================

            # Time Entries Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS time_entries (
                    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    clock_in TEXT NOT NULL,
                    clock_out TEXT,
                    break_minutes INTEGER DEFAULT 0,
                    work_type TEXT DEFAULT 'regular',
                    location TEXT DEFAULT 'office',
                    notes TEXT,
                    is_manual BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Timesheets Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS timesheets (
                    timesheet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    week_start TEXT NOT NULL,
                    week_end TEXT NOT NULL,
                    total_hours REAL DEFAULT 0,
                    regular_hours REAL DEFAULT 0,
                    overtime_hours REAL DEFAULT 0,
                    status TEXT DEFAULT 'draft',
                    submitted_date TEXT,
                    approved_by TEXT,
                    approved_date TEXT,
                    rejection_reason TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, week_start)
                )
            ''')

            # ==================== TRAINING & CERTIFICATIONS ====================

            # Training Courses Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS training_courses (
                    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    provider TEXT,
                    duration_hours REAL,
                    passing_score REAL DEFAULT 70,
                    is_mandatory BOOLEAN DEFAULT 0,
                    recertification_months INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Training Enrollments Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS training_enrollments (
                    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    course_id INTEGER NOT NULL,
                    enrolled_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    due_date TEXT,
                    started_date TEXT,
                    completed_date TEXT,
                    status TEXT DEFAULT 'enrolled',
                    score REAL,
                    attempts INTEGER DEFAULT 0,
                    certificate_path TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (course_id) REFERENCES training_courses(course_id)
                )
            ''')

            # Certifications Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS certifications (
                    cert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    issuing_body TEXT,
                    credential_id TEXT,
                    issue_date TEXT,
                    expiry_date TEXT,
                    document_path TEXT,
                    status TEXT DEFAULT 'active',
                    reminder_sent BOOLEAN DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ==================== PERFORMANCE APPRAISALS ====================

            # Appraisal Cycles Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS appraisal_cycles (
                    cycle_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    self_review_deadline TEXT,
                    manager_review_deadline TEXT,
                    status TEXT DEFAULT 'draft',
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Appraisal Records Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS appraisal_records (
                    appraisal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    reviewer_id TEXT,
                    self_rating REAL,
                    manager_rating REAL,
                    final_rating REAL,
                    self_comments TEXT,
                    manager_comments TEXT,
                    strengths TEXT,
                    areas_for_improvement TEXT,
                    development_plan TEXT,
                    status TEXT DEFAULT 'pending',
                    self_submitted_date TEXT,
                    manager_submitted_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cycle_id) REFERENCES appraisal_cycles(cycle_id),
                    UNIQUE(cycle_id, user_id)
                )
            ''')

            # Appraisal Goals Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS appraisal_goals (
                    goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    cycle_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'performance',
                    target_date TEXT,
                    progress INTEGER DEFAULT 0,
                    weight REAL DEFAULT 1.0,
                    status TEXT DEFAULT 'active',
                    completion_notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cycle_id) REFERENCES appraisal_cycles(cycle_id)
                )
            ''')

            # ==================== ONBOARDING/OFFBOARDING ====================

            # Onboarding Templates Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS onboarding_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    role TEXT,
                    department TEXT,
                    template_type TEXT DEFAULT 'onboarding',
                    estimated_days INTEGER DEFAULT 30,
                    is_active BOOLEAN DEFAULT 1,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Onboarding Template Tasks Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS onboarding_template_tasks (
                    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'general',
                    assigned_to_role TEXT DEFAULT 'employee',
                    due_days INTEGER DEFAULT 0,
                    is_required BOOLEAN DEFAULT 1,
                    order_num INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES onboarding_templates(template_id)
                )
            ''')

            # Onboarding Assignments Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS onboarding_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    template_id INTEGER NOT NULL,
                    assigned_by TEXT,
                    start_date TEXT NOT NULL,
                    target_completion_date TEXT,
                    actual_completion_date TEXT,
                    status TEXT DEFAULT 'in_progress',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES onboarding_templates(template_id)
                )
            ''')

            # Onboarding Task Progress Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS onboarding_task_progress (
                    progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id INTEGER NOT NULL,
                    task_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    assigned_to TEXT,
                    due_date TEXT,
                    completed_by TEXT,
                    completed_date TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assignment_id) REFERENCES onboarding_assignments(assignment_id),
                    FOREIGN KEY (task_id) REFERENCES onboarding_template_tasks(task_id),
                    UNIQUE(assignment_id, task_id)
                )
            ''')

            # ==================== INDEXES ====================

            # Leave indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_leave_requests_user
                ON leave_requests(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_leave_requests_status
                ON leave_requests(status)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_leave_balances_user
                ON leave_balances(user_id)
            ''')

            # Time indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_time_entries_user
                ON time_entries(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_time_entries_date
                ON time_entries(entry_date)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timesheets_user
                ON timesheets(user_id)
            ''')

            # Training indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_training_enrollments_user
                ON training_enrollments(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_certifications_user
                ON certifications(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_certifications_expiry
                ON certifications(expiry_date)
            ''')

            # Appraisal indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_appraisal_records_user
                ON appraisal_records(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_appraisal_goals_user
                ON appraisal_goals(user_id)
            ''')

            # Onboarding indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_onboarding_assignments_user
                ON onboarding_assignments(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_onboarding_task_progress_assignment
                ON onboarding_task_progress(assignment_id)
            ''')

            conn.commit()

            # Insert default leave types
            _insert_default_leave_types(cursor)
            conn.commit()

            print("Staff HR schemas initialized successfully")

    except sqlite3.Error as e:
        print(f"Error initializing Staff HR schemas: {e}")
        raise

def _insert_default_leave_types(cursor):
    """Insert default leave types if they don't exist."""
    default_types = [
        ('Annual Leave', 'Paid annual vacation leave', 25, 1, 1, '#27ae60'),
        ('Sick Leave', 'Leave for illness or medical appointments', 10, 1, 1, '#e74c3c'),
        ('Personal Leave', 'Leave for personal matters', 5, 1, 1, '#3498db'),
        ('Bereavement', 'Leave for family bereavement', 5, 0, 1, '#7f8c8d'),
        ('Parental Leave', 'Maternity/Paternity leave', 90, 1, 1, '#9b59b6'),
        ('Study Leave', 'Leave for educational purposes', 10, 1, 0, '#f39c12'),
        ('Unpaid Leave', 'Unpaid leave of absence', 30, 1, 0, '#95a5a6'),
        ('Emergency Leave', 'Emergency situations', 3, 0, 1, '#c0392b'),
    ]

    for leave_type in default_types:
        cursor.execute('''
            INSERT OR IGNORE INTO leave_types
            (name, description, max_days_per_year, requires_approval, is_paid, color_code)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', leave_type)

def _insert_default_training_courses(cursor):
    """Insert default training courses if they don't exist."""
    default_courses = [
        ('Health & Safety Basics', 'Essential health and safety training', 'Compliance', 2.0, 1),
        ('Data Protection & GDPR', 'Understanding data protection requirements', 'Compliance', 1.5, 1),
        ('Equality & Diversity', 'Workplace equality and diversity awareness', 'Compliance', 1.0, 1),
        ('Fire Safety', 'Fire safety procedures and evacuation', 'Safety', 1.0, 1),
        ('IT Security Awareness', 'Cybersecurity best practices', 'IT', 1.0, 1),
        ('First Aid Basics', 'Basic first aid training', 'Safety', 4.0, 0),
        ('Leadership Skills', 'Developing leadership capabilities', 'Development', 8.0, 0),
        ('Communication Skills', 'Effective workplace communication', 'Development', 4.0, 0),
    ]

    for course in default_courses:
        cursor.execute('''
            INSERT OR IGNORE INTO training_courses
            (name, description, category, duration_hours, is_mandatory)
            VALUES (?, ?, ?, ?, ?)
        ''', course)


# ======================================================================
# V2 schemas (Profiles, Teaching, Admin, Communication, Recruitment)
# ======================================================================

def init_staff_hr_v2_schemas():
    """Initialize all Staff HR v2 database tables."""
    with transaction() as conn:
        cursor = conn.cursor()

        # ============================================================
        # STAFF PROFILES & HR MANAGEMENT
        # ============================================================

        # Staff Profiles Extended
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff_profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                employee_id TEXT UNIQUE,
                department TEXT,
                job_title TEXT,
                employment_type TEXT DEFAULT 'full-time',
                hire_date TEXT,
                contract_end_date TEXT,
                manager_id TEXT,
                office_location TEXT,
                phone_extension TEXT,
                emergency_contact_name TEXT,
                emergency_contact_phone TEXT,
                emergency_contact_relationship TEXT,
                bio TEXT,
                expertise_areas TEXT,
                qualifications TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # staff_documents merged into unified documents table
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

        # Staff Workload Allocation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff_workload (
                workload_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                academic_year TEXT NOT NULL,
                semester TEXT,
                teaching_hours REAL DEFAULT 0,
                research_hours REAL DEFAULT 0,
                admin_hours REAL DEFAULT 0,
                service_hours REAL DEFAULT 0,
                total_fte REAL DEFAULT 1.0,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, academic_year, semester)
            )
        ''')

        # Staff Schedules
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff_schedules (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                day_of_week INTEGER,
                start_time TEXT,
                end_time TEXT,
                location TEXT,
                schedule_type TEXT DEFAULT 'office_hours',
                is_recurring INTEGER DEFAULT 1,
                effective_from TEXT,
                effective_to TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ============================================================
        # TEACHING & ACADEMIC STAFF
        # ============================================================

        # Teaching Portfolios
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teaching_portfolios (
                portfolio_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                teaching_philosophy TEXT,
                teaching_interests TEXT,
                courses_taught TEXT,
                teaching_innovations TEXT,
                awards_recognition TEXT,
                student_feedback_summary TEXT,
                professional_development TEXT,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Research Profiles
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS research_profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                research_interests TEXT,
                h_index INTEGER DEFAULT 0,
                total_citations INTEGER DEFAULT 0,
                total_publications INTEGER DEFAULT 0,
                orcid_id TEXT,
                google_scholar_id TEXT,
                researchgate_url TEXT,
                scopus_id TEXT,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Student Supervisions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_supervisions (
                supervision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                supervisor_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                student_name TEXT,
                program_type TEXT,
                thesis_title TEXT,
                start_date TEXT,
                expected_end_date TEXT,
                actual_end_date TEXT,
                status TEXT DEFAULT 'active',
                supervision_role TEXT DEFAULT 'primary',
                progress_notes TEXT,
                milestones TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # External Examiners
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS external_examiners (
                examiner_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                institution TEXT,
                email TEXT,
                phone TEXT,
                expertise_area TEXT,
                department TEXT,
                appointment_start TEXT,
                appointment_end TEXT,
                status TEXT DEFAULT 'active',
                contact_person_id TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Examiner Assignments
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS examiner_assignments (
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                examiner_id INTEGER NOT NULL,
                student_id TEXT,
                student_name TEXT,
                course_code TEXT,
                assignment_type TEXT,
                academic_year TEXT,
                report_submitted INTEGER DEFAULT 0,
                report_date TEXT,
                report_path TEXT,
                feedback TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (examiner_id) REFERENCES external_examiners(examiner_id)
            )
        ''')

        # Peer Observations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS peer_observations (
                observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                observer_id TEXT NOT NULL,
                observer_name TEXT,
                observee_id TEXT NOT NULL,
                observee_name TEXT,
                course_code TEXT,
                course_name TEXT,
                observation_date TEXT,
                observation_type TEXT DEFAULT 'peer',
                class_size INTEGER,
                duration_minutes INTEGER,
                strengths TEXT,
                areas_for_development TEXT,
                action_points TEXT,
                overall_rating INTEGER,
                status TEXT DEFAULT 'draft',
                acknowledged_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ============================================================
        # ADMINISTRATIVE TOOLS
        # ============================================================

        # Document Approvals
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_approvals (
                approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_type TEXT NOT NULL,
                document_title TEXT,
                document_description TEXT,
                document_path TEXT,
                submitted_by TEXT NOT NULL,
                submitted_by_name TEXT,
                submitted_date TEXT DEFAULT CURRENT_TIMESTAMP,
                current_approver TEXT,
                approval_chain TEXT,
                current_step INTEGER DEFAULT 1,
                total_steps INTEGER DEFAULT 1,
                status TEXT DEFAULT 'pending',
                comments TEXT,
                completed_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Document Approval History
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_approval_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                approval_id INTEGER NOT NULL,
                approver_id TEXT NOT NULL,
                approver_name TEXT,
                action TEXT,
                step_number INTEGER,
                comments TEXT,
                action_date TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (approval_id) REFERENCES document_approvals(approval_id)
            )
        ''')

        # Interdepartmental Requests
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interdepartmental_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_type TEXT NOT NULL,
                from_department TEXT,
                to_department TEXT,
                requested_by TEXT NOT NULL,
                requested_by_name TEXT,
                request_title TEXT NOT NULL,
                request_description TEXT,
                priority TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'pending',
                assigned_to TEXT,
                assigned_to_name TEXT,
                due_date TEXT,
                completed_date TEXT,
                response TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Access Cards
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS access_cards (
                card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_number TEXT UNIQUE NOT NULL,
                user_id TEXT,
                user_name TEXT,
                card_type TEXT DEFAULT 'staff',
                access_level TEXT,
                buildings_access TEXT,
                issue_date TEXT,
                expiry_date TEXT,
                status TEXT DEFAULT 'active',
                issued_by TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Key Assignments
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS key_assignments (
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_number TEXT NOT NULL,
                key_type TEXT,
                room_location TEXT,
                building TEXT,
                assigned_to TEXT,
                assigned_to_name TEXT,
                assigned_date TEXT,
                return_date TEXT,
                status TEXT DEFAULT 'assigned',
                issued_by TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Visitor Registrations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS visitor_registrations (
                visitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_name TEXT NOT NULL,
                visitor_email TEXT,
                visitor_phone TEXT,
                visitor_company TEXT,
                host_id TEXT NOT NULL,
                host_name TEXT,
                host_department TEXT,
                visit_purpose TEXT,
                scheduled_date TEXT,
                scheduled_time TEXT,
                check_in_time TEXT,
                check_out_time TEXT,
                badge_number TEXT,
                vehicle_registration TEXT,
                status TEXT DEFAULT 'scheduled',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ============================================================
        # COMMUNICATION & COLLABORATION
        # ============================================================

        # Staff Announcements
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff_announcements (
                announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                target_audience TEXT DEFAULT 'all',
                target_departments TEXT,
                target_roles TEXT,
                posted_by TEXT NOT NULL,
                posted_by_name TEXT,
                post_date TEXT DEFAULT CURRENT_TIMESTAMP,
                expiry_date TEXT,
                is_pinned INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                view_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Announcement Reads
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS announcement_reads (
                read_id INTEGER PRIMARY KEY AUTOINCREMENT,
                announcement_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                read_date TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(announcement_id, user_id),
                FOREIGN KEY (announcement_id) REFERENCES staff_announcements(announcement_id)
            )
        ''')

        # Committees
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS committees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                committee_type TEXT DEFAULT 'standing',
                department TEXT,
                chair_id TEXT,
                chair_name TEXT,
                secretary_id TEXT,
                secretary_name TEXT,
                meeting_frequency TEXT,
                meeting_location TEXT,
                is_active INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',
                created_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Committee Members
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS committee_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                committee_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                user_name TEXT,
                role TEXT DEFAULT 'member',
                start_date TEXT,
                end_date TEXT,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                joined_at TEXT,
                FOREIGN KEY (committee_id) REFERENCES committees(id),
                UNIQUE(committee_id, user_id)
            )
        ''')

        # Meeting Minutes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meeting_minutes (
                minutes_id INTEGER PRIMARY KEY AUTOINCREMENT,
                committee_id INTEGER,
                committee_name TEXT,
                meeting_title TEXT NOT NULL,
                meeting_date TEXT NOT NULL,
                meeting_time TEXT,
                location TEXT,
                attendees TEXT,
                apologies TEXT,
                agenda TEXT,
                minutes_content TEXT,
                action_items TEXT,
                decisions TEXT,
                next_meeting_date TEXT,
                recorded_by TEXT,
                recorded_by_name TEXT,
                approved_by TEXT,
                approved_date TEXT,
                status TEXT DEFAULT 'draft',
                document_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (committee_id) REFERENCES committees(id)
            )
        ''')

        # Staff Noticeboard
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff_noticeboard (
                notice_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                category TEXT DEFAULT 'general',
                posted_by TEXT NOT NULL,
                posted_by_name TEXT,
                contact_info TEXT,
                post_date TEXT DEFAULT CURRENT_TIMESTAMP,
                expiry_date TEXT,
                is_active INTEGER DEFAULT 1,
                view_count INTEGER DEFAULT 0
            )
        ''')

        # ============================================================
        # DEPARTMENT MANAGEMENT
        # ============================================================

        # Staff Recruitment Postings (renamed from job_postings to avoid conflict with Career Services)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff_recruitment_postings (
                posting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_title TEXT NOT NULL,
                department TEXT NOT NULL,
                job_type TEXT DEFAULT 'permanent',
                location TEXT,
                description TEXT,
                requirements TEXT,
                responsibilities TEXT,
                salary_range TEXT,
                benefits TEXT,
                posted_by TEXT NOT NULL,
                posted_by_name TEXT,
                post_date TEXT,
                closing_date TEXT,
                status TEXT DEFAULT 'draft',
                hiring_manager_id TEXT,
                hiring_manager_name TEXT,
                applications_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Staff Recruitment Applications (renamed from job_applications to avoid conflict)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff_recruitment_applications (
                application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                posting_id INTEGER NOT NULL,
                job_title TEXT,
                applicant_name TEXT NOT NULL,
                applicant_email TEXT NOT NULL,
                applicant_phone TEXT,
                applicant_address TEXT,
                cv_path TEXT,
                cover_letter_path TEXT,
                portfolio_url TEXT,
                application_date TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'received',
                shortlisted INTEGER DEFAULT 0,
                shortlisted_by TEXT,
                shortlisted_date TEXT,
                rejection_reason TEXT,
                notes TEXT,
                FOREIGN KEY (posting_id) REFERENCES staff_recruitment_postings(posting_id)
            )
        ''')

        # Interview Schedules
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interview_schedules (
                interview_id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL,
                applicant_name TEXT,
                interview_type TEXT DEFAULT 'in-person',
                interview_round INTEGER DEFAULT 1,
                interview_date TEXT,
                interview_time TEXT,
                duration_minutes INTEGER DEFAULT 60,
                location TEXT,
                video_link TEXT,
                interviewers TEXT,
                status TEXT DEFAULT 'scheduled',
                feedback TEXT,
                strengths TEXT,
                concerns TEXT,
                recommendation TEXT,
                overall_score INTEGER,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (application_id) REFERENCES staff_recruitment_applications(application_id)
            )
        ''')

        # Department KPIs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS department_kpis (
                kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
                department TEXT NOT NULL,
                kpi_name TEXT NOT NULL,
                kpi_description TEXT,
                kpi_category TEXT,
                target_value REAL,
                current_value REAL DEFAULT 0,
                unit TEXT,
                period TEXT DEFAULT 'annual',
                academic_year TEXT,
                quarter TEXT,
                status TEXT DEFAULT 'on_track',
                owner_id TEXT,
                owner_name TEXT,
                last_updated TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Budget Requests
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS budget_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                department TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                requested_by_name TEXT,
                request_title TEXT NOT NULL,
                request_description TEXT,
                amount_requested REAL NOT NULL,
                budget_category TEXT,
                justification TEXT,
                expected_benefits TEXT,
                supporting_docs TEXT,
                status TEXT DEFAULT 'pending',
                reviewed_by TEXT,
                reviewed_by_name TEXT,
                review_date TEXT,
                review_comments TEXT,
                approved_amount REAL,
                fiscal_year TEXT,
                priority TEXT DEFAULT 'normal',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ============================================================
        # INDEXES FOR PERFORMANCE
        # ============================================================

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_profiles_user ON staff_profiles(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_profiles_dept ON staff_profiles(department)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_owner ON documents(owner_id, owner_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_workload_user ON staff_workload(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_supervisions_supervisor ON student_supervisions(supervisor_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_supervisions_student ON student_supervisions(student_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_peer_obs_observer ON peer_observations(observer_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_peer_obs_observee ON peer_observations(observee_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_doc_approvals_status ON document_approvals(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_visitor_reg_date ON visitor_registrations(scheduled_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_announcements_active ON staff_announcements(is_active, post_date)')
        # Check if status column exists before creating index
        try:
            cursor.execute("SELECT status FROM job_postings LIMIT 0")
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_recruitment_postings_status ON staff_recruitment_postings(status)')
        except Exception:
            # Column doesn't exist, add it first
            try:
                cursor.execute('ALTER TABLE staff_recruitment_postings ADD COLUMN status TEXT DEFAULT "draft"')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_recruitment_postings_status ON staff_recruitment_postings(status)')
            except Exception:
                pass  # Column might already exist or table doesn't exist
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_recruitment_apps_posting ON staff_recruitment_applications(posting_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_kpis_dept ON department_kpis(department)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_budget_req_dept ON budget_requests(department)')

        # ============================================================
        # INSERT DEFAULT DATA
        # ============================================================

        # Default document types
        doc_types = [
            'contract', 'id_document', 'qualification', 'certification',
            'visa', 'right_to_work', 'dbs_check', 'reference', 'other'
        ]

        # Default request types
        request_types = [
            'IT Support', 'Facilities Request', 'HR Query', 'Finance Request',
            'Procurement', 'Event Support', 'Marketing Request', 'Other'
        ]

        # Default noticeboard categories
        notice_categories = [
            'for_sale', 'wanted', 'events', 'lost_found', 'housing', 'carpool', 'general'
        ]

        # Default KPI categories
        kpi_categories = [
            'research', 'teaching', 'student_satisfaction', 'finance', 'admin', 'hr'
        ]

        conn.commit()
        print("Staff HR v2 schemas initialized successfully")


def get_departments():
    """Get list of departments for dropdowns."""
    return [
        'Computer Science', 'Mathematics', 'Physics', 'Chemistry', 'Biology',
        'Engineering', 'Business', 'Economics', 'Law', 'Medicine',
        'Arts', 'Humanities', 'Social Sciences', 'Education', 'Nursing',
        'Administration', 'Finance', 'HR', 'IT Services', 'Facilities',
        'Library', 'Student Services', 'Research Office', 'Marketing', 'Other'
    ]


def get_employment_types():
    """Get list of employment types."""
    return ['full-time', 'part-time', 'contract', 'temporary', 'visiting', 'emeritus']


def get_program_types():
    """Get list of supervision program types."""
    return ['phd', 'mphil', 'masters', 'undergraduate', 'postdoc']


def get_observation_types():
    """Get list of peer observation types."""
    return ['formal', 'informal', 'peer', 'developmental', 'probationary']


def get_committee_types():
    """Get list of committee types."""
    return ['standing', 'ad-hoc', 'working-group', 'steering', 'advisory', 'examination']


def get_job_types():
    """Get list of job types."""
    return ['permanent', 'fixed-term', 'hourly', 'temporary', 'visiting']


def get_interview_types():
    """Get list of interview types."""
    return ['phone', 'video', 'in-person', 'panel', 'presentation', 'assessment']


# ======================================================================
# V3 schemas (Asset/Equipment Tracking)
# ======================================================================

def init_staff_hr_v3_schemas():
    """Initialize all Staff HR v3 database tables for asset tracking."""
    with transaction() as conn:
        cursor = conn.cursor()

        # ============================================================
        # ASSET/EQUIPMENT TRACKING
        # ============================================================

        # Asset Categories
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS asset_categories (
                category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                depreciation_years INTEGER DEFAULT 5,
                requires_approval INTEGER DEFAULT 0,
                parent_category_id INTEGER,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_category_id) REFERENCES asset_categories(category_id)
            )
        ''')

        # Assets/Equipment Master
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assets (
                asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_tag TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                category_id INTEGER NOT NULL,
                serial_number TEXT,
                manufacturer TEXT,
                model TEXT,
                purchase_date TEXT,
                purchase_price REAL,
                supplier TEXT,
                warranty_start TEXT,
                warranty_expiry TEXT,
                warranty_provider TEXT,
                current_value REAL,
                location TEXT,
                building TEXT,
                room TEXT,
                department TEXT,
                status TEXT DEFAULT 'available',
                condition TEXT DEFAULT 'good',
                last_inspection_date TEXT,
                next_inspection_date TEXT,
                disposal_date TEXT,
                disposal_method TEXT,
                disposal_value REAL,
                insurance_policy TEXT,
                insurance_value REAL,
                barcode TEXT,
                qr_code TEXT,
                image_path TEXT,
                notes TEXT,
                created_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES asset_categories(category_id)
            )
        ''')

        # Asset Assignments
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS asset_assignments (
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                user_name TEXT,
                user_department TEXT,
                assigned_by TEXT NOT NULL,
                assigned_by_name TEXT,
                assigned_date TEXT DEFAULT CURRENT_TIMESTAMP,
                expected_return_date TEXT,
                actual_return_date TEXT,
                return_condition TEXT,
                return_notes TEXT,
                return_processed_by TEXT,
                status TEXT DEFAULT 'active',
                purpose TEXT,
                location TEXT,
                acknowledgement_date TEXT,
                acknowledgement_signature TEXT,
                checkout_notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
            )
        ''')

        # Asset Issues
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS asset_issues (
                issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                reported_by TEXT NOT NULL,
                reported_by_name TEXT,
                reported_date TEXT DEFAULT CURRENT_TIMESTAMP,
                issue_type TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                priority TEXT DEFAULT 'normal',
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                impact TEXT,
                steps_to_reproduce TEXT,
                resolution TEXT,
                resolution_notes TEXT,
                resolved_by TEXT,
                resolved_by_name TEXT,
                resolved_date TEXT,
                resolution_cost REAL,
                status TEXT DEFAULT 'open',
                assigned_to TEXT,
                assigned_to_name TEXT,
                estimated_resolution_date TEXT,
                attachments TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
            )
        ''')

        # Asset Maintenance
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS asset_maintenance (
                maintenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                maintenance_type TEXT NOT NULL,
                maintenance_category TEXT DEFAULT 'routine',
                title TEXT,
                description TEXT,
                scheduled_date TEXT,
                scheduled_time TEXT,
                completed_date TEXT,
                performed_by TEXT,
                performed_by_name TEXT,
                vendor TEXT,
                vendor_contact TEXT,
                cost REAL DEFAULT 0,
                labor_cost REAL DEFAULT 0,
                parts_cost REAL DEFAULT 0,
                parts_replaced TEXT,
                work_performed TEXT,
                findings TEXT,
                recommendations TEXT,
                next_maintenance_date TEXT,
                next_maintenance_type TEXT,
                status TEXT DEFAULT 'scheduled',
                priority TEXT DEFAULT 'normal',
                downtime_hours REAL DEFAULT 0,
                attachments TEXT,
                approval_required INTEGER DEFAULT 0,
                approved_by TEXT,
                approved_date TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
            )
        ''')

        # Asset Audit Trail
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS asset_audit_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                action_category TEXT,
                action_by TEXT NOT NULL,
                action_by_name TEXT,
                action_date TEXT DEFAULT CURRENT_TIMESTAMP,
                old_values TEXT,
                new_values TEXT,
                field_changed TEXT,
                ip_address TEXT,
                user_agent TEXT,
                session_id TEXT,
                notes TEXT,
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
            )
        ''')

        # Asset Requests (for requesting new equipment)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS asset_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                requested_by TEXT NOT NULL,
                requested_by_name TEXT,
                department TEXT,
                category_id INTEGER,
                request_type TEXT DEFAULT 'new',
                item_name TEXT NOT NULL,
                item_description TEXT,
                quantity INTEGER DEFAULT 1,
                preferred_vendor TEXT,
                estimated_cost REAL,
                budget_code TEXT,
                justification TEXT,
                business_case TEXT,
                urgency TEXT DEFAULT 'normal',
                needed_by_date TEXT,
                status TEXT DEFAULT 'pending',
                reviewed_by TEXT,
                reviewed_by_name TEXT,
                review_date TEXT,
                review_comments TEXT,
                approved_by TEXT,
                approved_by_name TEXT,
                approved_date TEXT,
                rejection_reason TEXT,
                approved_amount REAL,
                fulfilled_date TEXT,
                fulfilled_asset_ids TEXT,
                attachments TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES asset_categories(category_id)
            )
        ''')

        # Asset Transfers (for tracking movement between departments/locations)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS asset_transfers (
                transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                from_location TEXT,
                from_department TEXT,
                from_user_id TEXT,
                to_location TEXT,
                to_department TEXT,
                to_user_id TEXT,
                transfer_date TEXT DEFAULT CURRENT_TIMESTAMP,
                transfer_reason TEXT,
                transferred_by TEXT NOT NULL,
                transferred_by_name TEXT,
                received_by TEXT,
                received_date TEXT,
                condition_at_transfer TEXT,
                status TEXT DEFAULT 'pending',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
            )
        ''')

        # Asset Depreciation Records
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS asset_depreciation (
                depreciation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                fiscal_year TEXT NOT NULL,
                period TEXT,
                depreciation_method TEXT DEFAULT 'straight-line',
                beginning_value REAL,
                depreciation_amount REAL,
                accumulated_depreciation REAL,
                ending_value REAL,
                calculated_date TEXT DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id),
                UNIQUE(asset_id, fiscal_year, period)
            )
        ''')

        # ============================================================
        # INDEXES FOR PERFORMANCE
        # ============================================================

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_tag ON assets(asset_tag)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_department ON assets(department)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_location ON assets(location)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_serial ON assets(serial_number)')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_assignments_asset ON asset_assignments(asset_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_assignments_user ON asset_assignments(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_assignments_status ON asset_assignments(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_assignments_date ON asset_assignments(assigned_date)')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_issues_asset ON asset_issues(asset_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_issues_status ON asset_issues(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_issues_severity ON asset_issues(severity)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_issues_reported ON asset_issues(reported_by)')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_maintenance_asset ON asset_maintenance(asset_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_maintenance_status ON asset_maintenance(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_maintenance_scheduled ON asset_maintenance(scheduled_date)')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_audit_asset ON asset_audit_log(asset_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_audit_action ON asset_audit_log(action)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_audit_date ON asset_audit_log(action_date)')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_requests_status ON asset_requests(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_requests_user ON asset_requests(requested_by)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_requests_dept ON asset_requests(department)')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_transfers_asset ON asset_transfers(asset_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_transfers_status ON asset_transfers(status)')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_depreciation_asset ON asset_depreciation(asset_id)')

        # ============================================================
        # INSERT DEFAULT DATA
        # ============================================================

        # Default asset categories
        default_categories = [
            ('Computers', 'Desktop and laptop computers', 5, 0),
            ('Monitors', 'Computer monitors and displays', 5, 0),
            ('Printers', 'Printers, scanners, and multifunction devices', 5, 0),
            ('Phones', 'Desk phones and mobile devices', 3, 0),
            ('Tablets', 'Tablets and mobile computing devices', 3, 0),
            ('Networking', 'Routers, switches, and network equipment', 7, 1),
            ('Servers', 'Servers and data center equipment', 7, 1),
            ('Storage', 'External storage and backup devices', 5, 0),
            ('Office Furniture', 'Desks, chairs, cabinets, and shelving', 10, 1),
            ('Lab Equipment', 'Laboratory and research equipment', 7, 1),
            ('Audio/Visual', 'Projectors, cameras, speakers, and AV equipment', 5, 1),
            ('Vehicles', 'University vehicles and transportation', 7, 1),
            ('Software Licenses', 'Software and subscription licenses', 1, 0),
            ('Medical Equipment', 'Medical and healthcare equipment', 7, 1),
            ('Sports Equipment', 'Sports and fitness equipment', 5, 0),
            ('Security Equipment', 'Security cameras, access systems', 7, 1),
            ('HVAC', 'Heating, ventilation, and air conditioning', 10, 1),
            ('Cleaning Equipment', 'Cleaning and maintenance equipment', 5, 0),
            ('Kitchen Equipment', 'Kitchen and catering equipment', 7, 0),
            ('Other', 'Other equipment and assets', 5, 0),
        ]

        for cat in default_categories:
            cursor.execute('''
                INSERT OR IGNORE INTO asset_categories
                (name, description, depreciation_years, requires_approval)
                VALUES (?, ?, ?, ?)
            ''', cat)

        conn.commit()
        print("Staff HR v3 schemas (Asset Tracking) initialized successfully")


def get_asset_statuses():
    """Get list of asset statuses."""
    return [
        'available', 'assigned', 'in_use', 'in_repair', 'in_maintenance',
        'reserved', 'lost', 'stolen', 'disposed', 'retired', 'pending_disposal'
    ]


def get_asset_conditions():
    """Get list of asset conditions."""
    return ['excellent', 'good', 'fair', 'poor', 'non_functional']


def get_issue_types():
    """Get list of issue types."""
    return [
        'hardware_failure', 'software_issue', 'physical_damage', 'malfunction',
        'performance_issue', 'connectivity_issue', 'missing_parts', 'wear_and_tear',
        'user_error', 'other'
    ]


def get_issue_severities():
    """Get list of issue severities."""
    return ['critical', 'high', 'medium', 'low']


def get_maintenance_types():
    """Get list of maintenance types."""
    return [
        'preventive', 'corrective', 'inspection', 'calibration', 'cleaning',
        'software_update', 'hardware_upgrade', 'replacement', 'routine', 'emergency'
    ]


def get_maintenance_categories():
    """Get list of maintenance categories."""
    return ['routine', 'scheduled', 'emergency', 'repair', 'upgrade']


def get_request_types():
    """Get list of asset request types."""
    return ['new', 'replacement', 'upgrade', 'temporary', 'project']


def get_request_urgencies():
    """Get list of request urgency levels."""
    return ['critical', 'high', 'normal', 'low']


def get_depreciation_methods():
    """Get list of depreciation methods."""
    return ['straight-line', 'declining-balance', 'units-of-production', 'sum-of-years']


def generate_asset_tag(category_id: int) -> str:
    """Generate a unique asset tag."""
    import datetime
    with get_connection() as conn:
        cursor = conn.cursor()

        # Get category prefix
        category = cursor.execute(
            'SELECT name FROM asset_categories WHERE category_id = ?',
            (category_id,)
        ).fetchone()

        prefix = 'AST'
        if category:
            # Create prefix from first 3 letters of category name
            prefix = category[0][:3].upper()

        # Get current year
        year = datetime.datetime.now().strftime('%y')

        # Get next sequence number for this prefix and year
        result = cursor.execute('''
            SELECT COUNT(*) FROM assets
            WHERE asset_tag LIKE ?
        ''', (f'{prefix}{year}%',)).fetchone()

        seq = (result[0] if result else 0) + 1

        return f'{prefix}{year}{seq:05d}'


# ======================================================================
# V4 schemas (Contracts, Expenses, Grievances, Disciplinary, Exit)
# ======================================================================

def init_staff_hr_v4_schemas():
    """Initialize all Staff HR v4 database tables."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # ==================== MIGRATION: Add missing columns ====================
            # Add status column to tables that might be missing it from earlier versions
            migration_columns = [
                ('expense_claims', 'status', "TEXT DEFAULT 'draft'"),
                ('grievances', 'status', "TEXT DEFAULT 'submitted'"),
                ('disciplinary_records', 'status', "TEXT DEFAULT 'under_review'"),
                ('staff_contracts', 'status', "TEXT DEFAULT 'active'"),
                ('exit_interviews', 'status', "TEXT DEFAULT 'scheduled'"),
            ]

            for table, column, column_def in migration_columns:
                try:
                    safe_alter_table_add_column(table, column, column_def, conn)
                except Exception:
                    pass  # Table doesn't exist yet, will be created below

            # ==================== CONTRACT MANAGEMENT ====================

            # Staff Contracts Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS staff_contracts (
                    contract_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    contract_type TEXT NOT NULL DEFAULT 'permanent',
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    salary REAL,
                    salary_currency TEXT DEFAULT 'GBP',
                    pay_frequency TEXT DEFAULT 'monthly',
                    terms TEXT,
                    status TEXT DEFAULT 'active',
                    renewal_date TEXT,
                    probation_end_date TEXT,
                    notice_period_days INTEGER DEFAULT 30,
                    working_hours_per_week REAL DEFAULT 37.5,
                    department TEXT,
                    job_title TEXT,
                    manager_id TEXT,
                    document_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT
                )
            ''')

            # Contract Amendments Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contract_amendments (
                    amendment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_id INTEGER NOT NULL,
                    change_type TEXT NOT NULL,
                    field_changed TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    effective_date TEXT NOT NULL,
                    reason TEXT,
                    approved_by TEXT,
                    approved_date TEXT,
                    status TEXT DEFAULT 'pending',
                    document_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (contract_id) REFERENCES staff_contracts(contract_id)
                )
            ''')

            # Probation Reviews Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS probation_reviews (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    contract_id INTEGER,
                    review_date TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    review_type TEXT DEFAULT 'mid-probation',
                    outcome TEXT,
                    performance_rating INTEGER,
                    strengths TEXT,
                    areas_for_improvement TEXT,
                    comments TEXT,
                    objectives_met TEXT,
                    recommendation TEXT,
                    next_review_date TEXT,
                    probation_extended BOOLEAN DEFAULT 0,
                    extension_reason TEXT,
                    extension_end_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (contract_id) REFERENCES staff_contracts(contract_id)
                )
            ''')

            # Contract Renewal Alerts Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contract_renewal_alerts (
                    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_id INTEGER NOT NULL,
                    alert_type TEXT NOT NULL,
                    alert_date TEXT NOT NULL,
                    days_before_expiry INTEGER,
                    sent BOOLEAN DEFAULT 0,
                    sent_date TEXT,
                    recipient_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (contract_id) REFERENCES staff_contracts(contract_id)
                )
            ''')

            # ==================== EXPENSE CLAIMS ====================

            # Expense Categories Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS expense_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    max_amount REAL,
                    requires_receipt BOOLEAN DEFAULT 1,
                    requires_approval BOOLEAN DEFAULT 1,
                    approval_threshold REAL,
                    is_active BOOLEAN DEFAULT 1,
                    gl_code TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Expense Claims Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS expense_claims (
                    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'GBP',
                    description TEXT NOT NULL,
                    expense_date TEXT NOT NULL,
                    receipt_path TEXT,
                    receipt_number TEXT,
                    project_code TEXT,
                    cost_center TEXT,
                    status TEXT DEFAULT 'draft',
                    submitted_date TEXT,
                    notes TEXT,
                    mileage_miles REAL,
                    mileage_rate REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES expense_categories(category_id)
                )
            ''')

            # Expense Approvals Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS expense_approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id INTEGER NOT NULL,
                    approver_id TEXT NOT NULL,
                    approval_level INTEGER DEFAULT 1,
                    decision TEXT,
                    comments TEXT,
                    decision_date TEXT,
                    amount_approved REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (claim_id) REFERENCES expense_claims(claim_id)
                )
            ''')

            # Reimbursements Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reimbursements (
                    reimbursement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'GBP',
                    payment_date TEXT,
                    payment_method TEXT,
                    reference_number TEXT,
                    bank_account_last4 TEXT,
                    status TEXT DEFAULT 'pending',
                    processed_by TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (claim_id) REFERENCES expense_claims(claim_id)
                )
            ''')

            # Expense Policies Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS expense_policies (
                    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    max_daily_amount REAL,
                    max_single_claim REAL,
                    requires_pre_approval_above REAL,
                    mileage_rate REAL DEFAULT 0.45,
                    subsistence_rate REAL,
                    applies_to_roles TEXT,
                    effective_from TEXT,
                    effective_to TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ==================== GRIEVANCE & DISCIPLINARY ====================

            # Grievance Categories Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grievance_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    severity_level INTEGER DEFAULT 1,
                    requires_investigation BOOLEAN DEFAULT 1,
                    sla_days INTEGER DEFAULT 30,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Grievances Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grievances (
                    grievance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference_number TEXT UNIQUE,
                    complainant_id TEXT NOT NULL,
                    respondent_id TEXT,
                    category_id INTEGER,
                    category_other TEXT,
                    subject TEXT NOT NULL,
                    description TEXT NOT NULL,
                    is_anonymous BOOLEAN DEFAULT 0,
                    is_confidential BOOLEAN DEFAULT 1,
                    status TEXT DEFAULT 'submitted',
                    priority TEXT DEFAULT 'normal',
                    assigned_to TEXT,
                    filed_date TEXT NOT NULL,
                    acknowledged_date TEXT,
                    investigation_start_date TEXT,
                    resolution_date TEXT,
                    resolution_type TEXT,
                    resolution_summary TEXT,
                    outcome TEXT,
                    appeal_deadline TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES grievance_categories(category_id)
                )
            ''')

            # Grievance Actions Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grievance_actions (
                    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grievance_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    action_date TEXT NOT NULL,
                    taken_by TEXT NOT NULL,
                    details TEXT,
                    outcome TEXT,
                    next_action TEXT,
                    next_action_date TEXT,
                    documents_path TEXT,
                    is_visible_to_complainant BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grievance_id) REFERENCES grievances(grievance_id)
                )
            ''')

            # Grievance Meetings Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grievance_meetings (
                    meeting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grievance_id INTEGER NOT NULL,
                    meeting_date TEXT NOT NULL,
                    meeting_time TEXT,
                    location TEXT,
                    attendees TEXT,
                    purpose TEXT,
                    minutes TEXT,
                    outcomes TEXT,
                    follow_up_actions TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grievance_id) REFERENCES grievances(grievance_id)
                )
            ''')

            # Disciplinary Records Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS disciplinary_records (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference_number TEXT UNIQUE,
                    user_id TEXT NOT NULL,
                    offense_type TEXT NOT NULL,
                    offense_category TEXT,
                    severity TEXT DEFAULT 'minor',
                    description TEXT NOT NULL,
                    date_occurred TEXT NOT NULL,
                    date_reported TEXT,
                    reported_by TEXT,
                    witnesses TEXT,
                    evidence_path TEXT,
                    status TEXT DEFAULT 'under_review',
                    investigation_notes TEXT,
                    is_confidential BOOLEAN DEFAULT 1,
                    previous_warnings INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Disciplinary Actions Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS disciplinary_actions (
                    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    action_level TEXT,
                    effective_date TEXT NOT NULL,
                    end_date TEXT,
                    duration_days INTEGER,
                    imposed_by TEXT NOT NULL,
                    reason TEXT,
                    conditions TEXT,
                    appeal_deadline TEXT,
                    appeal_submitted BOOLEAN DEFAULT 0,
                    appeal_outcome TEXT,
                    document_path TEXT,
                    acknowledged_by_employee BOOLEAN DEFAULT 0,
                    acknowledged_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (record_id) REFERENCES disciplinary_records(record_id)
                )
            ''')

            # Disciplinary Appeals Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS disciplinary_appeals (
                    appeal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_id INTEGER NOT NULL,
                    appellant_id TEXT NOT NULL,
                    appeal_date TEXT NOT NULL,
                    grounds TEXT NOT NULL,
                    supporting_documents TEXT,
                    status TEXT DEFAULT 'submitted',
                    hearing_date TEXT,
                    panel_members TEXT,
                    outcome TEXT,
                    outcome_date TEXT,
                    outcome_details TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (action_id) REFERENCES disciplinary_actions(action_id)
                )
            ''')

            # ==================== EXIT MANAGEMENT ====================

            # Exit Interviews Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exit_interviews (
                    interview_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    interviewer_id TEXT,
                    scheduled_date TEXT,
                    interview_date TEXT,
                    interview_method TEXT DEFAULT 'in_person',
                    status TEXT DEFAULT 'scheduled',
                    last_working_day TEXT,
                    tenure_months INTEGER,
                    department TEXT,
                    job_title TEXT,
                    manager_id TEXT,
                    reason_for_leaving TEXT,
                    reason_category TEXT,
                    destination TEXT,
                    new_employer TEXT,
                    new_role TEXT,
                    salary_factor BOOLEAN DEFAULT 0,
                    career_growth_factor BOOLEAN DEFAULT 0,
                    work_life_balance_factor BOOLEAN DEFAULT 0,
                    management_factor BOOLEAN DEFAULT 0,
                    culture_factor BOOLEAN DEFAULT 0,
                    job_satisfaction_rating INTEGER,
                    manager_rating INTEGER,
                    work_environment_rating INTEGER,
                    growth_opportunities_rating INTEGER,
                    compensation_rating INTEGER,
                    overall_rating INTEGER,
                    liked_most TEXT,
                    liked_least TEXT,
                    suggestions TEXT,
                    would_recommend BOOLEAN,
                    would_return BOOLEAN,
                    additional_comments TEXT,
                    confidential_notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Exit Checklist Templates Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exit_checklist_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    department TEXT,
                    role_type TEXT,
                    is_default BOOLEAN DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Exit Checklist Template Items Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exit_checklist_template_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    task_name TEXT NOT NULL,
                    description TEXT,
                    responsible_party TEXT,
                    category TEXT,
                    days_before_exit INTEGER DEFAULT 0,
                    is_mandatory BOOLEAN DEFAULT 1,
                    order_index INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES exit_checklist_templates(template_id)
                )
            ''')

            # Exit Checklist (User-specific) Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exit_checklist (
                    checklist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    template_id INTEGER,
                    task_name TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    responsible_party TEXT,
                    due_date TEXT,
                    completed BOOLEAN DEFAULT 0,
                    completed_date TEXT,
                    completed_by TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES exit_checklist_templates(template_id)
                )
            ''')

            # Knowledge Transfer Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS knowledge_transfer (
                    transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    departing_user_id TEXT NOT NULL,
                    receiving_user_id TEXT,
                    topic TEXT NOT NULL,
                    description TEXT,
                    documentation_path TEXT,
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'pending',
                    scheduled_date TEXT,
                    completed_date TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Turnover Analytics Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS turnover_analytics (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    department TEXT,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    period_type TEXT DEFAULT 'monthly',
                    headcount_start INTEGER DEFAULT 0,
                    headcount_end INTEGER DEFAULT 0,
                    voluntary_exits INTEGER DEFAULT 0,
                    involuntary_exits INTEGER DEFAULT 0,
                    retirements INTEGER DEFAULT 0,
                    transfers_out INTEGER DEFAULT 0,
                    new_hires INTEGER DEFAULT 0,
                    transfers_in INTEGER DEFAULT 0,
                    turnover_rate REAL,
                    retention_rate REAL,
                    avg_tenure_months REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Exit Reasons Summary Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exit_reasons_summary (
                    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period TEXT NOT NULL,
                    department TEXT,
                    reason_category TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    percentage REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.commit()

            # Create indexes for better performance
            _create_v4_indexes(cursor)
            conn.commit()

            # Insert default data
            _insert_v4_defaults(cursor)
            conn.commit()

            print("Staff HR v4 database schemas initialized successfully")
            return True

    except sqlite3.Error as e:
        print(f"Error initializing Staff HR v4 database: {e}")
        return False

def _create_v4_indexes(cursor):
    """Create indexes for v4 tables."""
    indexes = [
        # Contract indexes
        ('idx_contracts_user', 'staff_contracts', 'user_id'),
        ('idx_contracts_status', 'staff_contracts', 'status'),
        ('idx_contracts_end_date', 'staff_contracts', 'end_date'),
        ('idx_contracts_renewal', 'staff_contracts', 'renewal_date'),
        ('idx_amendments_contract', 'contract_amendments', 'contract_id'),
        ('idx_probation_user', 'probation_reviews', 'user_id'),

        # Expense indexes
        ('idx_expenses_user', 'expense_claims', 'user_id'),
        ('idx_expenses_status', 'expense_claims', 'status'),
        ('idx_expenses_date', 'expense_claims', 'expense_date'),
        ('idx_expense_approvals_claim', 'expense_approvals', 'claim_id'),
        ('idx_reimbursements_claim', 'reimbursements', 'claim_id'),

        # Grievance indexes
        ('idx_grievances_complainant', 'grievances', 'complainant_id'),
        ('idx_grievances_status', 'grievances', 'status'),
        ('idx_grievances_assigned', 'grievances', 'assigned_to'),
        ('idx_grievance_actions_grievance', 'grievance_actions', 'grievance_id'),

        # Disciplinary indexes
        ('idx_disciplinary_user', 'disciplinary_records', 'user_id'),
        ('idx_disciplinary_status', 'disciplinary_records', 'status'),
        ('idx_disciplinary_actions_record', 'disciplinary_actions', 'record_id'),

        # Exit indexes
        ('idx_exit_interviews_user', 'exit_interviews', 'user_id'),
        ('idx_exit_checklist_user', 'exit_checklist', 'user_id'),
        ('idx_turnover_period', 'turnover_analytics', 'period_start, period_end'),
    ]

    for idx_name, table, columns in indexes:
        try:
            cursor.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({columns})')
        except sqlite3.Error:
            pass  # Index may already exist

def _insert_v4_defaults(cursor):
    """Insert default data for v4 tables."""

    # Default expense categories
    expense_categories = [
        ('Travel - Domestic', 'Domestic travel expenses including flights, trains, buses', 500.00, 1, 1),
        ('Travel - International', 'International travel expenses', 2000.00, 1, 1),
        ('Accommodation', 'Hotel and lodging expenses', 200.00, 1, 1),
        ('Meals & Subsistence', 'Food and drink while working away', 50.00, 1, 1),
        ('Mileage', 'Personal vehicle mileage reimbursement', None, 0, 1),
        ('Office Supplies', 'Stationery and office equipment', 100.00, 1, 1),
        ('Training & Development', 'Course fees, books, materials', 500.00, 1, 1),
        ('Conference Fees', 'Registration fees for conferences', 1000.00, 1, 1),
        ('Equipment', 'Work-related equipment purchases', 500.00, 1, 1),
        ('Software & Subscriptions', 'Software licenses and subscriptions', 200.00, 1, 1),
        ('Communication', 'Phone, internet, postage', 50.00, 1, 1),
        ('Professional Memberships', 'Professional body membership fees', 300.00, 1, 1),
        ('Other', 'Miscellaneous expenses', 100.00, 1, 1),
    ]

    for name, desc, max_amt, req_receipt, req_approval in expense_categories:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO expense_categories
                (name, description, max_amount, requires_receipt, requires_approval)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, desc, max_amt, req_receipt, req_approval))
        except sqlite3.Error:
            pass

    # Default grievance categories
    grievance_categories = [
        ('Harassment', 'Workplace harassment including verbal, physical, or psychological', 3, 1, 14),
        ('Discrimination', 'Discrimination based on protected characteristics', 3, 1, 14),
        ('Bullying', 'Workplace bullying and intimidation', 3, 1, 14),
        ('Unfair Treatment', 'Perceived unfair treatment by management or colleagues', 2, 1, 21),
        ('Workload', 'Excessive or unreasonable workload issues', 1, 0, 30),
        ('Working Conditions', 'Health, safety, or environmental concerns', 2, 1, 21),
        ('Pay & Benefits', 'Issues related to compensation and benefits', 1, 0, 30),
        ('Policy Violation', 'Alleged violation of company policies', 2, 1, 21),
        ('Management Practices', 'Concerns about management decisions or practices', 1, 0, 30),
        ('Interpersonal Conflict', 'Conflicts with colleagues', 1, 0, 30),
        ('Other', 'Other grievances not covered above', 1, 0, 30),
    ]

    for name, desc, severity, req_inv, sla in grievance_categories:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO grievance_categories
                (name, description, severity_level, requires_investigation, sla_days)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, desc, severity, req_inv, sla))
        except sqlite3.Error:
            pass

    # Default exit checklist template
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO exit_checklist_templates
            (template_id, name, description, is_default, is_active)
            VALUES (1, 'Standard Exit Checklist', 'Default checklist for all departing employees', 1, 1)
        ''')
    except sqlite3.Error:
        pass

    # Default exit checklist items
    exit_items = [
        (1, 'Submit resignation letter', 'HR', 'Documentation', -14, 1, 1),
        (1, 'Schedule exit interview', 'HR', 'HR Process', -7, 1, 2),
        (1, 'Complete knowledge transfer', 'Manager', 'Handover', -7, 1, 3),
        (1, 'Return laptop and equipment', 'IT', 'Equipment', 0, 1, 4),
        (1, 'Return access cards and keys', 'Security', 'Access', 0, 1, 5),
        (1, 'Clear personal belongings', 'Employee', 'Personal', 0, 0, 6),
        (1, 'Settle expense claims', 'Finance', 'Finance', -3, 1, 7),
        (1, 'Update project documentation', 'Employee', 'Handover', -5, 1, 8),
        (1, 'Disable system access', 'IT', 'Access', 0, 1, 9),
        (1, 'Final paycheck processing', 'Payroll', 'Finance', 0, 1, 10),
        (1, 'Provide employment reference letter', 'HR', 'Documentation', 0, 0, 11),
        (1, 'COBRA/benefits continuation info', 'HR', 'Benefits', 0, 1, 12),
    ]

    for template_id, task, responsible, category, days_before, mandatory, order_idx in exit_items:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO exit_checklist_template_items
                (template_id, task_name, responsible_party, category,
                 days_before_exit, is_mandatory, order_index)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (template_id, task, responsible, category, days_before, mandatory, order_idx))
        except sqlite3.Error:
            pass

    # Default expense policy
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO expense_policies
            (policy_id, name, description, max_daily_amount, max_single_claim,
             requires_pre_approval_above, mileage_rate, is_active)
            VALUES (1, 'Standard Expense Policy', 'Default expense policy for all staff',
                    150.00, 1000.00, 500.00, 0.45, 1)
        ''')
    except sqlite3.Error:
        pass

# Make schema initialization available


# ======================================================================
# V5 schemas (Payroll, Faculty Schedules, Curriculum, Travel, Sabbaticals)
# ======================================================================

def init_staff_hr_v5_schemas():
    """Initialize all Staff HR v5 database tables."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # ==================== PAYROLL MANAGEMENT ====================

            # Payroll Periods Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payroll_periods (
                    period_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    period_type TEXT NOT NULL DEFAULT 'monthly',
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    payment_date TEXT,
                    status TEXT DEFAULT 'draft',
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Payroll Records Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payroll_records (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    contract_id INTEGER,
                    basic_salary REAL DEFAULT 0,
                    overtime_pay REAL DEFAULT 0,
                    allowances_total REAL DEFAULT 0,
                    gross_pay REAL DEFAULT 0,
                    tax_deduction REAL DEFAULT 0,
                    ni_deduction REAL DEFAULT 0,
                    pension_deduction REAL DEFAULT 0,
                    student_loan_deduction REAL DEFAULT 0,
                    other_deductions REAL DEFAULT 0,
                    net_pay REAL DEFAULT 0,
                    payment_status TEXT DEFAULT 'pending',
                    payment_reference TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (period_id) REFERENCES payroll_periods(period_id)
                )
            ''')

            # Tax Brackets Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tax_brackets (
                    bracket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tax_year TEXT NOT NULL,
                    bracket_name TEXT NOT NULL,
                    lower_limit REAL NOT NULL,
                    upper_limit REAL,
                    rate REAL NOT NULL,
                    personal_allowance REAL DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Payroll Allowances Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payroll_allowances (
                    allowance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    allowance_type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    frequency TEXT DEFAULT 'monthly',
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    is_active INTEGER DEFAULT 1,
                    approved_by TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Payroll Overtime Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payroll_overtime (
                    overtime_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    hours REAL NOT NULL,
                    rate_multiplier REAL DEFAULT 1.5,
                    reason TEXT,
                    status TEXT DEFAULT 'pending',
                    approved_by TEXT,
                    approved_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ==================== FACULTY SCHEDULE BUILDER ====================

            # Faculty Schedule Blocks Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS faculty_schedule_blocks (
                    block_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    day_of_week INTEGER NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    activity_type TEXT NOT NULL DEFAULT 'teaching',
                    title TEXT,
                    description TEXT,
                    location TEXT,
                    course_code TEXT,
                    color TEXT,
                    is_locked INTEGER DEFAULT 0,
                    semester TEXT,
                    academic_year TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Faculty Schedule Templates Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS faculty_schedule_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_by TEXT NOT NULL,
                    blocks_json TEXT NOT NULL,
                    is_shared INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Schedule Activity Types Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schedule_activity_types (
                    type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    color TEXT NOT NULL DEFAULT '#3498db',
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ==================== CURRICULUM DESIGN TOOLS ====================

            # Programmes Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS programmes (
                    programme_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    level TEXT NOT NULL DEFAULT 'undergraduate',
                    department TEXT,
                    total_credits INTEGER DEFAULT 360,
                    duration_years INTEGER DEFAULT 3,
                    description TEXT,
                    status TEXT DEFAULT 'draft',
                    created_by TEXT,
                    approved_by TEXT,
                    approved_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Programme Modules Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS programme_modules (
                    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    programme_id INTEGER NOT NULL,
                    module_code TEXT NOT NULL,
                    module_name TEXT,
                    year_of_study INTEGER NOT NULL DEFAULT 1,
                    semester INTEGER NOT NULL DEFAULT 1,
                    is_core INTEGER DEFAULT 1,
                    credits INTEGER DEFAULT 20,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id)
                )
            ''')

            # Learning Outcomes Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS learning_outcomes (
                    outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    programme_id INTEGER,
                    module_code TEXT,
                    code TEXT NOT NULL,
                    description TEXT NOT NULL,
                    bloom_level TEXT DEFAULT 'understand',
                    outcome_type TEXT DEFAULT 'programme',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id)
                )
            ''')

            # Outcome Alignments Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS outcome_alignments (
                    alignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    programme_outcome_id INTEGER NOT NULL,
                    module_outcome_id INTEGER NOT NULL,
                    alignment_strength TEXT DEFAULT 'moderate',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (programme_outcome_id) REFERENCES learning_outcomes(outcome_id),
                    FOREIGN KEY (module_outcome_id) REFERENCES learning_outcomes(outcome_id)
                )
            ''')

            # Syllabus Templates Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS syllabus_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    sections_json TEXT NOT NULL,
                    level TEXT DEFAULT 'undergraduate',
                    created_by TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Syllabi Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS syllabi (
                    syllabus_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_code TEXT NOT NULL,
                    academic_year TEXT NOT NULL,
                    template_id INTEGER,
                    content_json TEXT NOT NULL,
                    status TEXT DEFAULT 'draft',
                    created_by TEXT,
                    reviewed_by TEXT,
                    review_date TEXT,
                    review_comments TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES syllabus_templates(template_id)
                )
            ''')

            # Programme Approvals Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS programme_approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    programme_id INTEGER NOT NULL,
                    approval_level TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    comments TEXT,
                    reviewed_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id)
                )
            ''')

            # ==================== TRAVEL & CONFERENCE MANAGEMENT ====================

            # Travel Requests Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS travel_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_date TEXT NOT NULL,
                    return_date TEXT NOT NULL,
                    estimated_budget REAL DEFAULT 0,
                    budget_breakdown_json TEXT,
                    funding_source TEXT DEFAULT 'department',
                    status TEXT DEFAULT 'draft',
                    justification TEXT,
                    department TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Travel Itinerary Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS travel_itinerary (
                    leg_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    leg_order INTEGER NOT NULL DEFAULT 1,
                    transport_type TEXT NOT NULL DEFAULT 'flight',
                    departure_location TEXT,
                    arrival_location TEXT,
                    departure_datetime TEXT,
                    arrival_datetime TEXT,
                    booking_reference TEXT,
                    carrier TEXT,
                    cost REAL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES travel_requests(request_id)
                )
            ''')

            # Conference Registrations Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conference_registrations (
                    registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    travel_request_id INTEGER,
                    conference_name TEXT NOT NULL,
                    conference_url TEXT,
                    location TEXT,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    registration_fee REAL DEFAULT 0,
                    presentation_title TEXT,
                    presentation_type TEXT,
                    is_presenting INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'registered',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (travel_request_id) REFERENCES travel_requests(request_id)
                )
            ''')

            # Travel Approvals Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS travel_approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    approval_level TEXT NOT NULL,
                    approver_id TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    comments TEXT,
                    reviewed_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES travel_requests(request_id)
                )
            ''')

            # Travel Expenses Link Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS travel_expenses (
                    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    claim_id INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES travel_requests(request_id)
                )
            ''')

            # ==================== SABBATICAL / STUDY LEAVE ====================

            # Sabbatical Applications Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sabbatical_applications (
                    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    sabbatical_type TEXT DEFAULT 'research',
                    title TEXT NOT NULL,
                    research_proposal TEXT,
                    host_institution TEXT,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    pay_percentage REAL DEFAULT 100,
                    cover_arrangements TEXT,
                    funding_details TEXT,
                    status TEXT DEFAULT 'draft',
                    department TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Sabbatical Eligibility Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sabbatical_eligibility (
                    eligibility_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL UNIQUE,
                    years_of_service REAL DEFAULT 0,
                    last_sabbatical_end TEXT,
                    next_eligible_date TEXT,
                    is_eligible INTEGER DEFAULT 0,
                    notes TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Sabbatical Approvals Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sabbatical_approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    approval_level TEXT NOT NULL,
                    approver_id TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    comments TEXT,
                    reviewed_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (application_id) REFERENCES sabbatical_applications(application_id)
                )
            ''')

            # Sabbatical Progress Reports Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sabbatical_progress_reports (
                    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    report_type TEXT DEFAULT 'interim',
                    report_date TEXT NOT NULL,
                    content TEXT NOT NULL,
                    achievements TEXT,
                    challenges TEXT,
                    status TEXT DEFAULT 'submitted',
                    reviewer_id TEXT,
                    review_comments TEXT,
                    review_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (application_id) REFERENCES sabbatical_applications(application_id)
                )
            ''')

            # Sabbatical Return Plans Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sabbatical_return_plans (
                    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    return_date TEXT NOT NULL,
                    transition_period_weeks INTEGER DEFAULT 4,
                    research_outputs TEXT,
                    knowledge_sharing_plan TEXT,
                    meeting_scheduled INTEGER DEFAULT 0,
                    meeting_date TEXT,
                    status TEXT DEFAULT 'draft',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (application_id) REFERENCES sabbatical_applications(application_id)
                )
            ''')

            conn.commit()

            # Create indexes for better performance
            _create_v5_indexes(cursor)
            conn.commit()

            # Insert default data
            _insert_v5_defaults(cursor)
            conn.commit()

            print("Staff HR v5 database schemas initialized successfully")
            return True

    except sqlite3.Error as e:
        print(f"Error initializing Staff HR v5 database: {e}")
        return False

def _create_v5_indexes(cursor):
    """Create indexes for v5 tables."""
    indexes = [
        # Payroll indexes
        ('idx_payroll_records_period', 'payroll_records', 'period_id'),
        ('idx_payroll_records_user', 'payroll_records', 'user_id'),
        ('idx_payroll_overtime_user', 'payroll_overtime', 'user_id'),
        ('idx_payroll_overtime_status', 'payroll_overtime', 'status'),

        # Faculty schedule indexes
        ('idx_faculty_schedule_user', 'faculty_schedule_blocks', 'user_id'),
        ('idx_faculty_schedule_day', 'faculty_schedule_blocks', 'day_of_week'),

        # Curriculum design indexes
        ('idx_programmes_status', 'programmes', 'status'),
        ('idx_programmes_dept', 'programmes', 'department'),
        ('idx_programme_modules_prog', 'programme_modules', 'programme_id'),
        ('idx_learning_outcomes_prog', 'learning_outcomes', 'programme_id'),
        ('idx_syllabi_module', 'syllabi', 'module_code'),

        # Travel & conference indexes
        ('idx_travel_requests_user', 'travel_requests', 'user_id'),
        ('idx_travel_requests_status', 'travel_requests', 'status'),
        ('idx_conference_reg_user', 'conference_registrations', 'user_id'),

        # Sabbatical indexes
        ('idx_sabbatical_apps_user', 'sabbatical_applications', 'user_id'),
        ('idx_sabbatical_apps_status', 'sabbatical_applications', 'status'),
        ('idx_sabbatical_eligibility_user', 'sabbatical_eligibility', 'user_id'),
    ]

    for idx_name, table, columns in indexes:
        try:
            cursor.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({columns})')
        except sqlite3.Error:
            pass  # Index may already exist

def _insert_v5_defaults(cursor):
    """Insert default data for v5 tables."""
    import json

    # Default activity types
    default_activity_types = [
        ('teaching', 'Teaching', '#e74c3c', 1),
        ('office_hours', 'Office Hours', '#2ecc71', 2),
        ('meeting', 'Meeting', '#f39c12', 3),
        ('research', 'Research', '#3498db', 4),
        ('admin', 'Administration', '#9b59b6', 5),
        ('personal', 'Personal', '#95a5a6', 6),
    ]
    for name, display, color, order in default_activity_types:
        cursor.execute('''
            INSERT OR IGNORE INTO schedule_activity_types (name, display_name, color, sort_order)
            VALUES (?, ?, ?, ?)
        ''', (name, display, color, order))

    # Default UK 2025/26 tax brackets
    cursor.execute("SELECT COUNT(*) FROM tax_brackets WHERE tax_year = '2025/26'")
    if cursor.fetchone()[0] == 0:
        default_brackets = [
            ('2025/26', 'Personal Allowance', 0, 12570, 0, 12570),
            ('2025/26', 'Basic Rate', 12571, 50270, 0.20, 0),
            ('2025/26', 'Higher Rate', 50271, 125140, 0.40, 0),
            ('2025/26', 'Additional Rate', 125141, None, 0.45, 0),
        ]
        for year, name, lower, upper, rate, pa in default_brackets:
            cursor.execute('''
                INSERT INTO tax_brackets (tax_year, bracket_name, lower_limit, upper_limit, rate, personal_allowance)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (year, name, lower, upper, rate, pa))

    # Default syllabus template
    cursor.execute("SELECT COUNT(*) FROM syllabus_templates")
    if cursor.fetchone()[0] == 0:
        default_sections = json.dumps([
            {"title": "Module Overview", "required": True},
            {"title": "Learning Outcomes", "required": True},
            {"title": "Teaching Methods", "required": True},
            {"title": "Assessment Strategy", "required": True},
            {"title": "Reading List", "required": True},
            {"title": "Weekly Schedule", "required": False},
            {"title": "Academic Integrity", "required": True},
        ])
        cursor.execute('''
            INSERT INTO syllabus_templates (name, description, sections_json, level, created_by)
            VALUES (?, ?, ?, ?, ?)
        ''', ('Standard Undergraduate', 'Default template for undergraduate modules', default_sections, 'undergraduate', 'system'))

# Make schema initialization available


# ======================================================================
# V6 schemas (Committees, IP, Lab Booking, Cover, Workload, Directory)
# ======================================================================

def init_staff_hr_v6_schemas():
    """Initialize all Staff HR v6 database tables."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # ==================== COMMITTEE MANAGEMENT ====================

            # Committee Meetings Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS committee_meetings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    committee_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    meeting_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    location TEXT,
                    virtual_link TEXT,
                    status TEXT DEFAULT 'scheduled',
                    chair_id TEXT,
                    secretary_id TEXT,
                    recurrence TEXT DEFAULT 'none',
                    notes TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (committee_id) REFERENCES committees(id)
                )
            ''')

            # Meeting Agenda Items Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS committee_agenda_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meeting_id INTEGER NOT NULL,
                    item_order INTEGER NOT NULL DEFAULT 1,
                    title TEXT NOT NULL,
                    description TEXT,
                    item_type TEXT DEFAULT 'discussion',
                    presenter_id TEXT,
                    duration_minutes INTEGER DEFAULT 15,
                    resolution TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (meeting_id) REFERENCES committee_meetings(id)
                )
            ''')

            # Committee Votes Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS committee_votes (
                    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meeting_id INTEGER NOT NULL,
                    committee_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    vote_type TEXT DEFAULT 'simple_majority',
                    is_secret_ballot INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'open',
                    votes_for INTEGER DEFAULT 0,
                    votes_against INTEGER DEFAULT 0,
                    votes_abstain INTEGER DEFAULT 0,
                    result TEXT,
                    opened_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    closed_at TEXT,
                    created_by TEXT,
                    FOREIGN KEY (meeting_id) REFERENCES committee_meetings(id),
                    FOREIGN KEY (committee_id) REFERENCES committees(id)
                )
            ''')

            # Committee Ballots Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS committee_ballots (
                    ballot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vote_id INTEGER NOT NULL,
                    voter_id TEXT NOT NULL,
                    choice TEXT NOT NULL,
                    cast_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vote_id) REFERENCES committee_votes(vote_id),
                    UNIQUE(vote_id, voter_id)
                )
            ''')

            # Add meeting_id column to existing meeting_minutes table (from v2)
            try:
                safe_alter_table_add_column('meeting_minutes', 'meeting_id', 'INTEGER', conn)
            except Exception:
                pass  # Table may not exist yet if v2 schemas not initialized

            # ==================== INTELLECTUAL PROPERTY ====================

            # IP Disclosures Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ip_disclosures (
                    disclosure_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    ip_type TEXT DEFAULT 'invention',
                    development_stage TEXT DEFAULT 'concept',
                    funding_source TEXT,
                    department TEXT,
                    status TEXT DEFAULT 'draft',
                    submitted_date TEXT,
                    reviewed_by TEXT,
                    review_date TEXT,
                    review_comments TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Patents Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS patents (
                    patent_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    disclosure_id INTEGER,
                    patent_number TEXT,
                    title TEXT NOT NULL,
                    patent_office TEXT DEFAULT 'USPTO',
                    filing_date TEXT,
                    publication_date TEXT,
                    grant_date TEXT,
                    expiry_date TEXT,
                    status TEXT DEFAULT 'pending',
                    cost_to_date REAL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (disclosure_id) REFERENCES ip_disclosures(disclosure_id)
                )
            ''')

            # IP Inventors Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ip_inventors (
                    inventor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    disclosure_id INTEGER,
                    patent_id INTEGER,
                    user_id TEXT NOT NULL,
                    contribution_percentage REAL DEFAULT 0,
                    is_primary INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (disclosure_id) REFERENCES ip_disclosures(disclosure_id),
                    FOREIGN KEY (patent_id) REFERENCES patents(patent_id)
                )
            ''')

            # IP Licenses Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ip_licenses (
                    license_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patent_id INTEGER,
                    disclosure_id INTEGER,
                    licensee_name TEXT NOT NULL,
                    license_type TEXT DEFAULT 'non_exclusive',
                    royalty_rate REAL DEFAULT 0,
                    territory TEXT DEFAULT 'worldwide',
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    annual_fee REAL DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (patent_id) REFERENCES patents(patent_id),
                    FOREIGN KEY (disclosure_id) REFERENCES ip_disclosures(disclosure_id)
                )
            ''')

            # IP Revenue Shares Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ip_revenue_shares (
                    revenue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_id INTEGER NOT NULL,
                    period TEXT NOT NULL,
                    total_revenue REAL DEFAULT 0,
                    university_share REAL DEFAULT 0,
                    inventor_share REAL DEFAULT 0,
                    department_share REAL DEFAULT 0,
                    payment_date TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (license_id) REFERENCES ip_licenses(license_id)
                )
            ''')

            # ==================== LAB / EQUIPMENT BOOKING ====================

            # Equipment Categories Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS equipment_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    parent_category_id INTEGER,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parent_category_id) REFERENCES equipment_categories(category_id)
                )
            ''')

            # Lab Equipment Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS lab_equipment (
                    equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category_id INTEGER,
                    location TEXT,
                    building TEXT,
                    room_number TEXT,
                    serial_number TEXT,
                    model TEXT,
                    manufacturer TEXT,
                    status TEXT DEFAULT 'available',
                    max_booking_hours INTEGER DEFAULT 8,
                    min_booking_hours INTEGER DEFAULT 1,
                    requires_approval INTEGER DEFAULT 0,
                    requires_training INTEGER DEFAULT 0,
                    description TEXT,
                    image_url TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES equipment_categories(category_id)
                )
            ''')

            # Equipment Bookings Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS equipment_bookings (
                    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    booking_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    purpose TEXT,
                    status TEXT DEFAULT 'pending',
                    approved_by TEXT,
                    approved_date TEXT,
                    checked_in_at TEXT,
                    checked_out_at TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (equipment_id) REFERENCES lab_equipment(equipment_id)
                )
            ''')

            # Equipment Maintenance Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS equipment_maintenance (
                    maintenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_id INTEGER NOT NULL,
                    maintenance_type TEXT DEFAULT 'routine',
                    description TEXT,
                    scheduled_date TEXT,
                    completed_date TEXT,
                    performed_by TEXT,
                    cost REAL DEFAULT 0,
                    status TEXT DEFAULT 'scheduled',
                    next_due_date TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (equipment_id) REFERENCES lab_equipment(equipment_id)
                )
            ''')

            # Booking Rules Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS booking_rules (
                    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_id INTEGER,
                    category_id INTEGER,
                    rule_type TEXT NOT NULL,
                    rule_value TEXT NOT NULL,
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (equipment_id) REFERENCES lab_equipment(equipment_id),
                    FOREIGN KEY (category_id) REFERENCES equipment_categories(category_id)
                )
            ''')

            # ==================== SUBSTITUTE / COVER ARRANGEMENTS ====================

            # Teaching Qualifications Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teaching_qualifications (
                    qualification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    subject_area TEXT NOT NULL,
                    course_code TEXT,
                    qualification_level TEXT DEFAULT 'qualified',
                    verified INTEGER DEFAULT 0,
                    verified_by TEXT,
                    verified_date TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Cover Skills Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cover_skills (
                    skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    skill_name TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    proficiency TEXT DEFAULT 'intermediate',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Cover Requests Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cover_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    requester_id TEXT NOT NULL,
                    request_type TEXT DEFAULT 'teaching',
                    course_code TEXT,
                    course_name TEXT,
                    cover_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    location TEXT,
                    reason TEXT,
                    urgency TEXT DEFAULT 'normal',
                    status TEXT DEFAULT 'open',
                    department TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Cover Offers Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cover_offers (
                    offer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    volunteer_id TEXT NOT NULL,
                    message TEXT,
                    status TEXT DEFAULT 'offered',
                    offered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES cover_requests(request_id)
                )
            ''')

            # Cover Assignments Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cover_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    assignee_id TEXT NOT NULL,
                    assigned_by TEXT,
                    accepted INTEGER DEFAULT 0,
                    accepted_date TEXT,
                    completed INTEGER DEFAULT 0,
                    completed_date TEXT,
                    feedback TEXT,
                    rating INTEGER,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES cover_requests(request_id)
                )
            ''')

            # ==================== WORKLOAD DASHBOARD ====================

            # Workload Norms Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workload_norms (
                    norm_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    department TEXT,
                    role TEXT,
                    teaching_pct REAL DEFAULT 40,
                    research_pct REAL DEFAULT 40,
                    admin_pct REAL DEFAULT 10,
                    service_pct REAL DEFAULT 10,
                    total_hours_per_week REAL DEFAULT 40,
                    is_default INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Workload Allocations Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workload_allocations (
                    allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    academic_year TEXT NOT NULL,
                    semester TEXT,
                    activity_name TEXT NOT NULL,
                    activity_type TEXT NOT NULL DEFAULT 'teaching',
                    hours_per_week REAL DEFAULT 0,
                    weighting_factor REAL DEFAULT 1.0,
                    weighted_hours REAL DEFAULT 0,
                    notes TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ==================== STAFF DIRECTORY ====================

            # Staff Expertise Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS staff_expertise (
                    expertise_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    expertise_area TEXT NOT NULL,
                    category TEXT DEFAULT 'academic',
                    proficiency TEXT DEFAULT 'intermediate',
                    keywords TEXT,
                    is_public INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Staff Office Hours Directory Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS staff_office_hours_directory (
                    hours_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    day_of_week INTEGER NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    location TEXT,
                    virtual_link TEXT,
                    is_by_appointment INTEGER DEFAULT 0,
                    semester TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.commit()

            # Create indexes for better performance
            _create_v6_indexes(cursor)
            conn.commit()

            # Insert default data
            _insert_v6_defaults(cursor)
            conn.commit()

            print("Staff HR v6 database schemas initialized successfully")
            return True

    except sqlite3.Error as e:
        print(f"Error initializing Staff HR v6 database: {e}")
        return False

def _create_v6_indexes(cursor):
    """Create indexes for v6 tables."""
    indexes = [
        # Committee indexes
        ('idx_committee_meetings_committee', 'committee_meetings', 'committee_id'),
        ('idx_committee_meetings_date', 'committee_meetings', 'meeting_date'),
        ('idx_committee_meetings_status', 'committee_meetings', 'status'),
        ('idx_meeting_agenda_meeting', 'committee_agenda_items', 'meeting_id'),
        ('idx_committee_votes_meeting', 'committee_votes', 'meeting_id'),
        ('idx_committee_votes_committee', 'committee_votes', 'committee_id'),
        ('idx_committee_ballots_vote', 'committee_ballots', 'vote_id'),

        # IP indexes
        ('idx_ip_disclosures_status', 'ip_disclosures', 'status'),
        ('idx_ip_disclosures_creator', 'ip_disclosures', 'created_by'),
        ('idx_patents_disclosure', 'patents', 'disclosure_id'),
        ('idx_patents_status', 'patents', 'status'),
        ('idx_ip_inventors_user', 'ip_inventors', 'user_id'),
        ('idx_ip_inventors_disclosure', 'ip_inventors', 'disclosure_id'),
        ('idx_ip_licenses_patent', 'ip_licenses', 'patent_id'),

        # Equipment indexes
        ('idx_lab_equipment_category', 'lab_equipment', 'category_id'),
        ('idx_lab_equipment_status', 'lab_equipment', 'status'),
        ('idx_equipment_bookings_equipment', 'equipment_bookings', 'equipment_id'),
        ('idx_equipment_bookings_user', 'equipment_bookings', 'user_id'),
        ('idx_equipment_bookings_date', 'equipment_bookings', 'booking_date'),
        ('idx_equipment_bookings_status', 'equipment_bookings', 'status'),
        ('idx_equipment_maintenance_equipment', 'equipment_maintenance', 'equipment_id'),

        # Cover indexes
        ('idx_teaching_quals_user', 'teaching_qualifications', 'user_id'),
        ('idx_cover_skills_user', 'cover_skills', 'user_id'),
        ('idx_cover_requests_requester', 'cover_requests', 'requester_id'),
        ('idx_cover_requests_status', 'cover_requests', 'status'),
        ('idx_cover_requests_date', 'cover_requests', 'cover_date'),
        ('idx_cover_offers_request', 'cover_offers', 'request_id'),
        ('idx_cover_assignments_request', 'cover_assignments', 'request_id'),
        ('idx_cover_assignments_assignee', 'cover_assignments', 'assignee_id'),

        # Workload indexes
        ('idx_workload_allocations_user', 'workload_allocations', 'user_id'),
        ('idx_workload_allocations_year', 'workload_allocations', 'academic_year'),
        ('idx_workload_norms_dept', 'workload_norms', 'department'),

        # Directory indexes
        ('idx_staff_expertise_user', 'staff_expertise', 'user_id'),
        ('idx_staff_expertise_category', 'staff_expertise', 'category'),
        ('idx_staff_office_hours_user', 'staff_office_hours_directory', 'user_id'),
    ]

    for idx_name, table, columns in indexes:
        try:
            cursor.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({columns})')
        except sqlite3.Error:
            pass  # Index may already exist

def _insert_v6_defaults(cursor):
    """Insert default data for v6 tables."""

    # Default equipment categories
    default_categories = [
        ('Lab Instruments', 'Scientific laboratory instruments and tools'),
        ('Computing', 'Computers, servers, and computing hardware'),
        ('Audio Visual', 'Projectors, cameras, and AV equipment'),
        ('Workshop', 'Workshop tools and machinery'),
        ('Measurement', 'Measurement and testing equipment'),
        ('Safety', 'Safety equipment and protective gear'),
    ]
    for name, desc in default_categories:
        cursor.execute('''
            INSERT OR IGNORE INTO equipment_categories (name, description)
            VALUES (?, ?)
        ''', (name, desc))

    # Default workload norms
    cursor.execute("SELECT COUNT(*) FROM workload_norms")
    if cursor.fetchone()[0] == 0:
        default_norms = [
            ('Teaching-Focused', None, 'lecturer', 60, 20, 10, 10, 40, 0),
            ('Research-Focused', None, 'researcher', 20, 60, 10, 10, 40, 0),
            ('Balanced', None, None, 40, 40, 10, 10, 40, 1),
            ('Administrative', None, 'administrator', 10, 10, 70, 10, 40, 0),
        ]
        for name, dept, role, teach, research, admin, service, hours, is_default in default_norms:
            cursor.execute('''
                INSERT INTO workload_norms (
                    name, department, role, teaching_pct, research_pct,
                    admin_pct, service_pct, total_hours_per_week, is_default
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, dept, role, teach, research, admin, service, hours, is_default))


# Make schema initialization available


# ======================================================================
# V7 schemas (Mentoring, Grant Budgets, Peer Review, Comm Hub, Teaching Load)
# ======================================================================

def init_staff_hr_v7_schemas():
    """Initialize all Staff HR v7 database tables."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # ==================== MENTORING PROGRAMME ====================

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS staff_mentoring_programmes (
                    programme_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    programme_type TEXT DEFAULT 'general',
                    department TEXT,
                    max_mentees_per_mentor INTEGER DEFAULT 3,
                    duration_months INTEGER DEFAULT 12,
                    status TEXT DEFAULT 'active',
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS staff_mentors (
                    mentor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    programme_id INTEGER NOT NULL,
                    expertise_areas TEXT,
                    max_mentees INTEGER DEFAULT 3,
                    current_mentees INTEGER DEFAULT 0,
                    availability TEXT DEFAULT 'available',
                    bio TEXT,
                    status TEXT DEFAULT 'active',
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (programme_id) REFERENCES staff_mentoring_programmes(programme_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS staff_mentoring_matches (
                    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    programme_id INTEGER NOT NULL,
                    mentor_id INTEGER NOT NULL,
                    mentee_user_id TEXT NOT NULL,
                    match_reason TEXT,
                    status TEXT DEFAULT 'proposed',
                    start_date TEXT,
                    expected_end_date TEXT,
                    actual_end_date TEXT,
                    mentor_rating INTEGER,
                    mentee_rating INTEGER,
                    notes TEXT,
                    matched_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (programme_id) REFERENCES staff_mentoring_programmes(programme_id),
                    FOREIGN KEY (mentor_id) REFERENCES staff_mentors(mentor_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS staff_mentoring_sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER NOT NULL,
                    session_date TEXT NOT NULL,
                    duration_minutes INTEGER DEFAULT 60,
                    session_type TEXT DEFAULT 'one_on_one',
                    location TEXT,
                    virtual_link TEXT,
                    topics_discussed TEXT,
                    action_items TEXT,
                    mentor_notes TEXT,
                    mentee_notes TEXT,
                    status TEXT DEFAULT 'scheduled',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES staff_mentoring_matches(match_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS staff_mentoring_goals (
                    goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    target_date TEXT,
                    completion_date TEXT,
                    status TEXT DEFAULT 'in_progress',
                    progress_pct INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES staff_mentoring_matches(match_id)
                )
            ''')

            # ==================== GRANT BUDGET TRACKING ====================

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grant_budget_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grant_budget_allocations (
                    allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grant_application_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    allocated_amount REAL DEFAULT 0,
                    spent_amount REAL DEFAULT 0,
                    committed_amount REAL DEFAULT 0,
                    remaining_amount REAL DEFAULT 0,
                    alert_threshold_pct REAL DEFAULT 80,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grant_application_id) REFERENCES grant_applications(grant_application_id),
                    FOREIGN KEY (category_id) REFERENCES grant_budget_categories(category_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grant_expense_items (
                    expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grant_application_id INTEGER NOT NULL,
                    allocation_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    amount REAL NOT NULL,
                    expense_date TEXT,
                    vendor TEXT,
                    receipt_path TEXT,
                    invoice_number TEXT,
                    status TEXT DEFAULT 'draft',
                    submitted_by TEXT,
                    approved_by TEXT,
                    approved_date TEXT,
                    payment_reference TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grant_application_id) REFERENCES grant_applications(grant_application_id),
                    FOREIGN KEY (allocation_id) REFERENCES grant_budget_allocations(allocation_id),
                    FOREIGN KEY (category_id) REFERENCES grant_budget_categories(category_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grant_funding_alerts (
                    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grant_application_id INTEGER NOT NULL,
                    allocation_id INTEGER,
                    alert_type TEXT DEFAULT 'threshold',
                    severity TEXT DEFAULT 'info',
                    message TEXT NOT NULL,
                    is_read INTEGER DEFAULT 0,
                    is_resolved INTEGER DEFAULT 0,
                    triggered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TEXT,
                    resolved_by TEXT,
                    FOREIGN KEY (grant_application_id) REFERENCES grant_applications(grant_application_id),
                    FOREIGN KEY (allocation_id) REFERENCES grant_budget_allocations(allocation_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grant_budget_transfers (
                    transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grant_application_id INTEGER NOT NULL,
                    from_allocation_id INTEGER NOT NULL,
                    to_allocation_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    reason TEXT,
                    status TEXT DEFAULT 'pending',
                    requested_by TEXT,
                    approved_by TEXT,
                    approved_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grant_application_id) REFERENCES grant_applications(grant_application_id),
                    FOREIGN KEY (from_allocation_id) REFERENCES grant_budget_allocations(allocation_id),
                    FOREIGN KEY (to_allocation_id) REFERENCES grant_budget_allocations(allocation_id)
                )
            ''')

            # ==================== PEER REVIEW / COLLABORATION ====================

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS peer_review_cycles (
                    cycle_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    cycle_type TEXT DEFAULT 'teaching_materials',
                    department TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    status TEXT DEFAULT 'draft',
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS peer_review_submissions (
                    submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id INTEGER NOT NULL,
                    submitter_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    material_type TEXT DEFAULT 'other',
                    course_code TEXT,
                    file_path TEXT,
                    file_name TEXT,
                    version INTEGER DEFAULT 1,
                    parent_submission_id INTEGER,
                    status TEXT DEFAULT 'draft',
                    submitted_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cycle_id) REFERENCES peer_review_cycles(cycle_id),
                    FOREIGN KEY (parent_submission_id) REFERENCES peer_review_submissions(submission_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS peer_review_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    assigned_by TEXT,
                    due_date TEXT,
                    status TEXT DEFAULT 'assigned',
                    assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    FOREIGN KEY (submission_id) REFERENCES peer_review_submissions(submission_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS peer_review_feedback (
                    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id INTEGER NOT NULL,
                    submission_id INTEGER NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    overall_rating INTEGER,
                    content_quality INTEGER,
                    clarity INTEGER,
                    alignment_with_outcomes INTEGER,
                    engagement_potential INTEGER,
                    strengths TEXT,
                    improvements TEXT,
                    detailed_comments TEXT,
                    recommendation TEXT DEFAULT 'approve',
                    is_confidential INTEGER DEFAULT 0,
                    submitted_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assignment_id) REFERENCES peer_review_assignments(assignment_id),
                    FOREIGN KEY (submission_id) REFERENCES peer_review_submissions(submission_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS peer_review_shared_resources (
                    resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    resource_type TEXT DEFAULT 'template',
                    subject_area TEXT,
                    course_code TEXT,
                    file_path TEXT,
                    file_name TEXT,
                    shared_by TEXT NOT NULL,
                    download_count INTEGER DEFAULT 0,
                    rating_sum INTEGER DEFAULT 0,
                    rating_count INTEGER DEFAULT 0,
                    is_approved INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS peer_review_resource_ratings (
                    rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resource_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    comment TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (resource_id) REFERENCES peer_review_shared_resources(resource_id),
                    UNIQUE(resource_id, user_id)
                )
            ''')

            # ==================== COMMUNICATION HUB ====================

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comm_hub_forums (
                    forum_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    forum_type TEXT DEFAULT 'topic',
                    department TEXT,
                    visibility TEXT DEFAULT 'public',
                    is_archived INTEGER DEFAULT 0,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comm_hub_forum_members (
                    member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    forum_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT DEFAULT 'member',
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (forum_id) REFERENCES comm_hub_forums(forum_id),
                    UNIQUE(forum_id, user_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comm_hub_threads (
                    thread_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    forum_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT,
                    author_id TEXT NOT NULL,
                    is_pinned INTEGER DEFAULT 0,
                    is_locked INTEGER DEFAULT 0,
                    view_count INTEGER DEFAULT 0,
                    reply_count INTEGER DEFAULT 0,
                    last_reply_at TEXT,
                    last_reply_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (forum_id) REFERENCES comm_hub_forums(forum_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comm_hub_replies (
                    reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id INTEGER NOT NULL,
                    parent_reply_id INTEGER,
                    content TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    is_solution INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (thread_id) REFERENCES comm_hub_threads(thread_id),
                    FOREIGN KEY (parent_reply_id) REFERENCES comm_hub_replies(reply_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comm_hub_polls (
                    poll_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    forum_id INTEGER,
                    thread_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    poll_type TEXT DEFAULT 'single_choice',
                    is_anonymous INTEGER DEFAULT 0,
                    allow_comments INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'open',
                    closes_at TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (forum_id) REFERENCES comm_hub_forums(forum_id),
                    FOREIGN KEY (thread_id) REFERENCES comm_hub_threads(thread_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comm_hub_poll_options (
                    option_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    poll_id INTEGER NOT NULL,
                    option_text TEXT NOT NULL,
                    display_order INTEGER DEFAULT 0,
                    vote_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (poll_id) REFERENCES comm_hub_polls(poll_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comm_hub_poll_votes (
                    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    poll_id INTEGER NOT NULL,
                    option_id INTEGER NOT NULL,
                    voter_id TEXT NOT NULL,
                    comment TEXT,
                    voted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (poll_id) REFERENCES comm_hub_polls(poll_id),
                    FOREIGN KEY (option_id) REFERENCES comm_hub_poll_options(option_id),
                    UNIQUE(poll_id, option_id, voter_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comm_hub_pinned_messages (
                    pin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_type TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    pinned_by TEXT NOT NULL,
                    pinned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT,
                    context TEXT DEFAULT 'global'
                )
            ''')

            # ==================== TEACHING LOAD MANAGEMENT ====================

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teaching_load_courses (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    course_code TEXT NOT NULL,
                    course_name TEXT,
                    section TEXT,
                    academic_year TEXT NOT NULL,
                    semester TEXT NOT NULL,
                    credit_hours REAL DEFAULT 3.0,
                    contact_hours_pw REAL DEFAULT 3.0,
                    lecture_hours_pw REAL,
                    lab_hours_pw REAL,
                    tutorial_hours_pw REAL,
                    enrolled_students INTEGER DEFAULT 0,
                    max_enrollment INTEGER DEFAULT 30,
                    class_size_factor REAL DEFAULT 1.0,
                    weighted_hours REAL DEFAULT 0,
                    department TEXT,
                    is_new_prep INTEGER DEFAULT 0,
                    is_team_taught INTEGER DEFAULT 0,
                    team_share_pct REAL DEFAULT 100,
                    status TEXT DEFAULT 'assigned',
                    source TEXT DEFAULT 'manual',
                    notes TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teaching_load_release_time (
                    release_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    academic_year TEXT NOT NULL,
                    semester TEXT NOT NULL,
                    release_type TEXT DEFAULT 'other',
                    title TEXT NOT NULL,
                    hours_per_week REAL DEFAULT 0,
                    credit_equivalent REAL DEFAULT 0,
                    start_date TEXT,
                    end_date TEXT,
                    funding_source TEXT,
                    status TEXT DEFAULT 'pending',
                    approved_by TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teaching_load_standards (
                    standard_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    department TEXT,
                    role TEXT,
                    standard_credits REAL DEFAULT 12,
                    standard_courses INTEGER DEFAULT 4,
                    max_credits REAL DEFAULT 15,
                    max_new_preps INTEGER DEFAULT 2,
                    large_class_threshold INTEGER DEFAULT 50,
                    large_class_factor REAL DEFAULT 1.25,
                    overload_rate REAL DEFAULT 0,
                    is_default INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teaching_load_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    academic_year TEXT NOT NULL,
                    semester TEXT NOT NULL,
                    total_courses INTEGER DEFAULT 0,
                    total_credits REAL DEFAULT 0,
                    total_contact_hours REAL DEFAULT 0,
                    total_weighted_hours REAL DEFAULT 0,
                    total_students INTEGER DEFAULT 0,
                    release_hours REAL DEFAULT 0,
                    net_load_credits REAL DEFAULT 0,
                    is_overloaded INTEGER DEFAULT 0,
                    overload_credits REAL DEFAULT 0,
                    snapshot_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, academic_year, semester)
                )
            ''')

            conn.commit()

            # Create indexes
            _create_v7_indexes(cursor)
            conn.commit()

            # Insert defaults
            _insert_v7_defaults(cursor)
            conn.commit()

            print("Staff HR v7 database schemas initialized successfully")
            return True

    except sqlite3.Error as e:
        print(f"Error initializing Staff HR v7 database: {e}")
        return False


def _create_v7_indexes(cursor):
    """Create indexes for v7 tables."""
    indexes = [
        # Mentoring indexes
        ('idx_staff_mentors_user', 'staff_mentors', 'user_id'),
        ('idx_staff_mentors_programme', 'staff_mentors', 'programme_id'),
        ('idx_staff_mentors_status', 'staff_mentors', 'availability'),
        ('idx_mentoring_matches_programme', 'staff_mentoring_matches', 'programme_id'),
        ('idx_mentoring_matches_mentor', 'staff_mentoring_matches', 'mentor_id'),
        ('idx_mentoring_matches_mentee', 'staff_mentoring_matches', 'mentee_user_id'),
        ('idx_mentoring_matches_status', 'staff_mentoring_matches', 'status'),
        ('idx_mentoring_sessions_match', 'staff_mentoring_sessions', 'match_id'),
        ('idx_mentoring_sessions_date', 'staff_mentoring_sessions', 'session_date'),
        ('idx_mentoring_goals_match', 'staff_mentoring_goals', 'match_id'),
        ('idx_mentoring_goals_status', 'staff_mentoring_goals', 'status'),

        # Grant budget indexes
        ('idx_grant_alloc_grant', 'grant_budget_allocations', 'grant_application_id'),
        ('idx_grant_alloc_category', 'grant_budget_allocations', 'category_id'),
        ('idx_grant_expense_grant', 'grant_expense_items', 'grant_application_id'),
        ('idx_grant_expense_status', 'grant_expense_items', 'status'),
        ('idx_grant_expense_date', 'grant_expense_items', 'expense_date'),
        ('idx_grant_expense_submitted', 'grant_expense_items', 'submitted_by'),
        ('idx_grant_alerts_grant', 'grant_funding_alerts', 'grant_application_id'),
        ('idx_grant_alerts_read', 'grant_funding_alerts', 'is_read'),
        ('idx_grant_transfers_grant', 'grant_budget_transfers', 'grant_application_id'),
        ('idx_grant_transfers_status', 'grant_budget_transfers', 'status'),

        # Peer review indexes
        ('idx_pr_submissions_cycle', 'peer_review_submissions', 'cycle_id'),
        ('idx_pr_submissions_submitter', 'peer_review_submissions', 'submitter_id'),
        ('idx_pr_submissions_status', 'peer_review_submissions', 'status'),
        ('idx_pr_submissions_parent', 'peer_review_submissions', 'parent_submission_id'),
        ('idx_pr_assignments_submission', 'peer_review_assignments', 'submission_id'),
        ('idx_pr_assignments_reviewer', 'peer_review_assignments', 'reviewer_id'),
        ('idx_pr_assignments_status', 'peer_review_assignments', 'status'),
        ('idx_pr_feedback_assignment', 'peer_review_feedback', 'assignment_id'),
        ('idx_pr_feedback_submission', 'peer_review_feedback', 'submission_id'),
        ('idx_pr_resources_type', 'peer_review_shared_resources', 'resource_type'),
        ('idx_pr_resources_shared_by', 'peer_review_shared_resources', 'shared_by'),
        ('idx_pr_resources_approved', 'peer_review_shared_resources', 'is_approved'),
        ('idx_pr_resource_ratings_resource', 'peer_review_resource_ratings', 'resource_id'),
        ('idx_pr_cycles_status', 'peer_review_cycles', 'status'),
        ('idx_pr_cycles_type', 'peer_review_cycles', 'cycle_type'),
        ('idx_pr_feedback_reviewer', 'peer_review_feedback', 'reviewer_id'),

        # Comm hub indexes
        ('idx_comm_forums_type', 'comm_hub_forums', 'forum_type'),
        ('idx_comm_forums_dept', 'comm_hub_forums', 'department'),
        ('idx_comm_members_forum', 'comm_hub_forum_members', 'forum_id'),
        ('idx_comm_members_user', 'comm_hub_forum_members', 'user_id'),
        ('idx_comm_threads_forum', 'comm_hub_threads', 'forum_id'),
        ('idx_comm_threads_author', 'comm_hub_threads', 'author_id'),
        ('idx_comm_threads_pinned', 'comm_hub_threads', 'is_pinned'),
        ('idx_comm_replies_thread', 'comm_hub_replies', 'thread_id'),
        ('idx_comm_replies_parent', 'comm_hub_replies', 'parent_reply_id'),
        ('idx_comm_polls_forum', 'comm_hub_polls', 'forum_id'),
        ('idx_comm_polls_thread', 'comm_hub_polls', 'thread_id'),
        ('idx_comm_polls_status', 'comm_hub_polls', 'status'),
        ('idx_comm_poll_options_poll', 'comm_hub_poll_options', 'poll_id'),
        ('idx_comm_poll_votes_poll', 'comm_hub_poll_votes', 'poll_id'),
        ('idx_comm_pinned_context', 'comm_hub_pinned_messages', 'context'),

        # Teaching load indexes
        ('idx_tl_courses_user', 'teaching_load_courses', 'user_id'),
        ('idx_tl_courses_year', 'teaching_load_courses', 'academic_year'),
        ('idx_tl_courses_semester', 'teaching_load_courses', 'semester'),
        ('idx_tl_courses_code', 'teaching_load_courses', 'course_code'),
        ('idx_tl_courses_status', 'teaching_load_courses', 'status'),
        ('idx_tl_courses_dept', 'teaching_load_courses', 'department'),
        ('idx_tl_release_user', 'teaching_load_release_time', 'user_id'),
        ('idx_tl_release_year', 'teaching_load_release_time', 'academic_year'),
        ('idx_tl_release_status', 'teaching_load_release_time', 'status'),
        ('idx_tl_standards_dept', 'teaching_load_standards', 'department'),
        ('idx_tl_standards_role', 'teaching_load_standards', 'role'),
        ('idx_tl_history_user', 'teaching_load_history', 'user_id'),
        ('idx_tl_history_year', 'teaching_load_history', 'academic_year'),
    ]

    for idx_name, table, columns in indexes:
        try:
            cursor.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({columns})')
        except sqlite3.Error:
            pass


def _insert_v7_defaults(cursor):
    """Insert default data for v7 tables."""

    # Default mentoring programmes
    cursor.execute("SELECT COUNT(*) FROM staff_mentoring_programmes")
    if cursor.fetchone()[0] == 0:
        default_programmes = [
            ('Research Mentoring', 'Pair experienced researchers with early-career academics', 'research'),
            ('Teaching Excellence', 'Mentoring for teaching skills development', 'teaching'),
            ('New Staff Buddy', 'Buddy system for newly joined staff', 'buddy'),
            ('Leadership Development', 'Preparing future academic leaders', 'leadership'),
        ]
        for name, desc, ptype in default_programmes:
            cursor.execute('''
                INSERT INTO staff_mentoring_programmes (name, description, programme_type, status)
                VALUES (?, ?, ?, 'active')
            ''', (name, desc, ptype))

    # Default grant budget categories
    default_budget_cats = [
        ('Personnel', 'Salaries, benefits, and stipends', 1),
        ('Equipment', 'Research equipment and instruments', 2),
        ('Travel', 'Conference travel and fieldwork', 3),
        ('Supplies', 'Lab supplies and consumables', 4),
        ('Subcontracts', 'Subcontractor and consultant fees', 5),
        ('Publication', 'Publication and dissemination costs', 6),
        ('Indirect Costs', 'Overhead and institutional costs', 7),
        ('Other', 'Miscellaneous expenses', 8),
    ]
    for name, desc, order in default_budget_cats:
        cursor.execute('''
            INSERT OR IGNORE INTO grant_budget_categories (name, description, sort_order)
            VALUES (?, ?, ?)
        ''', (name, desc, order))

    # Default comm hub forums
    cursor.execute("SELECT COUNT(*) FROM comm_hub_forums")
    if cursor.fetchone()[0] == 0:
        default_forums = [
            ('General Discussion', 'Open discussion for all staff', 'topic', 'public'),
            ('Staff Social', 'Social events, interests, and community', 'social', 'public'),
            ('Policy Updates', 'University policy discussions and feedback', 'topic', 'public'),
        ]
        for name, desc, ftype, vis in default_forums:
            cursor.execute('''
                INSERT INTO comm_hub_forums (name, description, forum_type, visibility)
                VALUES (?, ?, ?, ?)
            ''', (name, desc, ftype, vis))

    # Default teaching load standards
    cursor.execute("SELECT COUNT(*) FROM teaching_load_standards")
    if cursor.fetchone()[0] == 0:
        default_standards = [
            (None, 'Professor', 9, 3, 12, 2, 50, 1.25, 0, 0),
            (None, 'Associate Professor', 12, 4, 15, 2, 50, 1.25, 0, 0),
            (None, 'Assistant Professor', 12, 4, 15, 2, 50, 1.25, 0, 0),
            (None, 'Lecturer', 15, 5, 18, 3, 50, 1.25, 0, 0),
            (None, None, 12, 4, 15, 2, 50, 1.25, 0, 1),
        ]
        for dept, role, std_cr, std_co, max_cr, max_np, lct, lcf, olr, is_def in default_standards:
            cursor.execute('''
                INSERT INTO teaching_load_standards (
                    department, role, standard_credits, standard_courses,
                    max_credits, max_new_preps, large_class_threshold,
                    large_class_factor, overload_rate, is_default
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (dept, role, std_cr, std_co, max_cr, max_np, lct, lcf, olr, is_def))


# ======================================================================
# Master initialization function
# ======================================================================

def init_all_staff_hr_schemas():
    """Initialize all Staff HR database schemas (v1 through v7)."""
    init_staff_hr_schemas()
    init_staff_hr_v2_schemas()
    init_staff_hr_v3_schemas()
    init_staff_hr_v4_schemas()
    init_staff_hr_v5_schemas()
    init_staff_hr_v6_schemas()
    init_staff_hr_v7_schemas()

