"""Staff HR schemas — Governance (committees, recruitment, grievance/disciplinary, KPIs, IP, announcements, comm hub, directory).

Auto-grouped from the former staff_hr_schemas_all.py by domain, not by the
historical _init_staff_hr_vN_schemas sprint numbering.

Idempotent. Safe to call repeatedly: every statement is CREATE TABLE
IF NOT EXISTS / CREATE INDEX IF NOT EXISTS / INSERT OR IGNORE.
"""
from __future__ import annotations

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    get_connection,
)
from education_system.university_system.core.sql_safety import (
    safe_alter_table_add_column,
)


def _init_governance_schemas() -> None:
    """Create every governance-domain Staff HR table."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # ---- staff_announcements ----
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

            # ---- announcement_reads ----
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

            # ---- committees ----
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

            # ---- committee_members ----
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

            # ---- meeting_minutes ----
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

            # ---- staff_noticeboard ----
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

            # ---- staff_recruitment_postings ----
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

            # ---- staff_recruitment_applications ----
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

            # ---- interview_schedules ----
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

            # ---- department_kpis ----
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

            # ---- budget_requests ----
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

            # ---- staff_announcements ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_announcements_active ON staff_announcements(is_active, post_date)')

            # ---- staff_recruitment_postings ----
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

            # ---- staff_recruitment_applications ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_recruitment_apps_posting ON staff_recruitment_applications(posting_id)')

            # ---- department_kpis ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_kpis_dept ON department_kpis(department)')

            # ---- budget_requests ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_budget_req_dept ON budget_requests(department)')

            doc_types = [
                'contract', 'id_document', 'qualification', 'certification',
                'visa', 'right_to_work', 'dbs_check', 'reference', 'other'
            ]

            request_types = [
                'IT Support', 'Facilities Request', 'HR Query', 'Finance Request',
                'Procurement', 'Event Support', 'Marketing Request', 'Other'
            ]

            notice_categories = [
                'for_sale', 'wanted', 'events', 'lost_found', 'housing', 'carpool', 'general'
            ]

            kpi_categories = [
                'research', 'teaching', 'student_satisfaction', 'finance', 'admin', 'hr'
            ]

            cursor = conn.cursor()

            # ---- grievance_categories ----
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

            # ---- grievances ----
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

            # ---- grievance_actions ----
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

            # ---- grievance_meetings ----
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

            # ---- disciplinary_records ----
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

            # ---- disciplinary_actions ----
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

            # ---- disciplinary_appeals ----
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

            # ---- committee_meetings ----
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

            # ---- committee_agenda_items ----
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

            # ---- committee_votes ----
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

            # ---- committee_ballots ----
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

            try:
                safe_alter_table_add_column('meeting_minutes', 'meeting_id', 'INTEGER', conn)
            except Exception:
                pass  # Table may not exist yet if v2 schemas not initialized

            # ---- ip_disclosures ----
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

            # ---- patents ----
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

            # ---- ip_inventors ----
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

            # ---- ip_licenses ----
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

            # ---- ip_revenue_shares ----
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

            # ---- staff_expertise ----
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

            # ---- staff_office_hours_directory ----
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

            return True

            cursor = conn.cursor()

            # ---- comm_hub_forums ----
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

            # ---- comm_hub_forum_members ----
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

            # ---- comm_hub_threads ----
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

            # ---- comm_hub_replies ----
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

            # ---- comm_hub_polls ----
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

            # ---- comm_hub_poll_options ----
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

            # ---- comm_hub_poll_votes ----
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

            # ---- comm_hub_pinned_messages ----
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

            conn.commit()
    except sqlite3.Error as exc:
        print(f"Error initialising Staff HR governance schemas: {exc}")
        raise


def get_departments():
    """Get list of departments for dropdowns."""
    return [
        'Computer Science', 'Mathematics', 'Physics', 'Chemistry', 'Biology',
        'Engineering', 'Business', 'Economics', 'Law', 'Medicine',
        'Arts', 'Humanities', 'Social Sciences', 'Education', 'Nursing',
        'Administration', 'Finance', 'HR', 'IT Services', 'Facilities',
        'Library', 'Student Services', 'Research Office', 'Marketing', 'Other'
    ]


def get_committee_types():
    """Get list of committee types."""
    return ['standing', 'ad-hoc', 'working-group', 'steering', 'advisory', 'examination']


def get_job_types():
    """Get list of job types."""
    return ['permanent', 'fixed-term', 'hourly', 'temporary', 'visiting']


def get_interview_types():
    """Get list of interview types."""
    return ['phone', 'video', 'in-person', 'panel', 'presentation', 'assessment']
