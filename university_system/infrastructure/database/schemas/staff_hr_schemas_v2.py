"""
Staff HR Database Schemas - Version 2 (Extended Features)

Additional tables for:
- Staff Profiles & Documents
- Teaching & Academic Staff
- Administrative Tools
- Communication & Collaboration
- Department Management
"""

from university_system.infrastructure.database.db import get_connection, transaction


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

        # Staff Documents
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff_documents (
                document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                document_type TEXT,
                document_name TEXT NOT NULL,
                file_path TEXT,
                issue_date TEXT,
                expiry_date TEXT,
                status TEXT DEFAULT 'active',
                uploaded_by TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
                committee_id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Committee Members
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS committee_members (
                membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                committee_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                user_name TEXT,
                role TEXT DEFAULT 'member',
                start_date TEXT,
                end_date TEXT,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                FOREIGN KEY (committee_id) REFERENCES committees(committee_id),
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
                FOREIGN KEY (committee_id) REFERENCES committees(committee_id)
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
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_documents_user ON staff_documents(user_id)')
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
