"""Staff HR schemas — Academic (teaching, research, supervisions, curriculum, sabbaticals, mentoring, peer review).

Auto-grouped from the former staff_hr_schemas_all.py by domain, not by the
historical _init_staff_hr_vN_schemas sprint numbering.

Idempotent. Safe to call repeatedly: every statement is CREATE TABLE
IF NOT EXISTS / CREATE INDEX IF NOT EXISTS / INSERT OR IGNORE.
"""
from __future__ import annotations

from education_system.post_18.university_system.infrastructure.database.db import (
    sqlite3,
    get_connection,
)
from education_system.post_18.university_system.core.sql_safety import (
    safe_alter_table_add_column,
)


def _relax_notnull_column(cursor, table, column, create_new_sql, tmp_name, columns) -> None:
    """Idempotently drop a NOT NULL constraint on ``table.column``.

    The approver/reviewer columns on the approval tables are populated later,
    at approval time, not when the pending approval rows are first created.
    Older live databases declared these columns NOT NULL, which broke the
    submit flow. This rebuilds the table without the NOT NULL constraint,
    preserving all existing rows. Guarded by PRAGMA table_info so it only
    runs when the column is still NOT NULL and is safe to run repeatedly.
    """
    info = cursor.execute(f"PRAGMA table_info({table})").fetchall()
    notnull = {row[1]: row[3] for row in info}
    # Skip if the table doesn't exist yet or the column is already nullable.
    if column not in notnull or not notnull[column]:
        return
    col_list = ", ".join(columns)
    cursor.execute(create_new_sql)
    cursor.execute(
        f"INSERT INTO {tmp_name} ({col_list}) SELECT {col_list} FROM {table}"
    )
    cursor.execute(f"DROP TABLE {table}")
    cursor.execute(f"ALTER TABLE {tmp_name} RENAME TO {table}")


def _init_academic_schemas() -> None:
    """Create every academic-domain Staff HR table."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # ---- teaching_portfolios ----
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

            # ---- research_profiles ----
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

            # ---- student_supervisions ----
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

            # ---- external_examiners ----
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

            # ---- examiner_assignments ----
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

            # ---- peer_observations ----
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

            # ---- student_supervisions ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_supervisions_supervisor ON student_supervisions(supervisor_id)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_supervisions_student ON student_supervisions(student_id)')

            # ---- peer_observations ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_peer_obs_observer ON peer_observations(observer_id)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_peer_obs_observee ON peer_observations(observee_id)')

            # ---- programmes ----
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

            # ---- programme_modules ----
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

            # ---- learning_outcomes ----
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

            # ---- outcome_alignments ----
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

            # ---- syllabus_templates ----
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

            # ---- syllabi ----
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

            # ---- programme_approvals ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS programme_approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    programme_id INTEGER NOT NULL,
                    approval_level TEXT NOT NULL,
                    reviewer_id TEXT,
                    status TEXT DEFAULT 'pending',
                    comments TEXT,
                    reviewed_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id)
                )
            ''')

            # ---- sabbatical_applications ----
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

            # ---- sabbatical_eligibility ----
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

            # ---- sabbatical_approvals ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sabbatical_approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    approval_level TEXT NOT NULL,
                    approver_id TEXT,
                    status TEXT DEFAULT 'pending',
                    comments TEXT,
                    reviewed_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (application_id) REFERENCES sabbatical_applications(application_id)
                )
            ''')

            # ---- sabbatical_progress_reports ----
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

            # ---- sabbatical_return_plans ----
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

            # ---- migration: relax NOT NULL on approver/reviewer columns ----
            # These are assigned at approval time, not when the pending rows
            # are created at submit time. Self-heal legacy live databases.
            _relax_notnull_column(
                cursor, 'sabbatical_approvals', 'approver_id',
                '''CREATE TABLE sabbatical_approvals_new (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    approval_level TEXT NOT NULL,
                    approver_id TEXT,
                    status TEXT DEFAULT 'pending',
                    comments TEXT,
                    reviewed_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (application_id) REFERENCES sabbatical_applications(application_id)
                )''',
                'sabbatical_approvals_new',
                ['approval_id', 'application_id', 'approval_level', 'approver_id',
                 'status', 'comments', 'reviewed_date', 'created_at'],
            )
            _relax_notnull_column(
                cursor, 'programme_approvals', 'reviewer_id',
                '''CREATE TABLE programme_approvals_new (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    programme_id INTEGER NOT NULL,
                    approval_level TEXT NOT NULL,
                    reviewer_id TEXT,
                    status TEXT DEFAULT 'pending',
                    comments TEXT,
                    reviewed_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id)
                )''',
                'programme_approvals_new',
                ['approval_id', 'programme_id', 'approval_level', 'reviewer_id',
                 'status', 'comments', 'reviewed_date', 'created_at'],
            )

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

            import json

            default_activity_types = [
                ('teaching', 'Teaching', '#e74c3c', 1),
                ('office_hours', 'Office Hours', '#2ecc71', 2),
                ('meeting', 'Meeting', '#f39c12', 3),
                ('research', 'Research', '#3498db', 4),
                ('admin', 'Administration', '#9b59b6', 5),
                ('personal', 'Personal', '#95a5a6', 6),
            ]

            # schedule_activity_types is created by the workload init, which runs
            # AFTER this one, so on a fresh DB the table isn't there yet. Guard
            # like the core reference-data seeds — it populates on a later init
            # pass once the owning module has created the table.
            try:
                for name, display, color, order in default_activity_types:
                    cursor.execute('''
                        INSERT OR IGNORE INTO schedule_activity_types (name, display_name, color, sort_order)
                        VALUES (?, ?, ?, ?)
                    ''', (name, display, color, order))
            except sqlite3.Error:
                pass  # table created by a later-running init module

            # tax_brackets is created by the finance init (runs later) — same guard.
            try:
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
            except sqlite3.Error:
                pass  # table created by a later-running init module

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

            # ---- staff_mentoring_programmes ----
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

            # ---- staff_mentors ----
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

            # ---- staff_mentoring_matches ----
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

            # ---- staff_mentoring_sessions ----
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

            # ---- staff_mentoring_goals ----
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

            # ---- peer_review_cycles ----
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

            # ---- peer_review_submissions ----
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

            # ---- hr_peer_review_assignments ----
            # Prefixed with hr_ to avoid colliding with the academics
            # assignment_system / core_schemas table also named
            # `peer_review_assignments` (which owns a different schema).
            # Columns use created_at/updated_at to match PeerReviewManager.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hr_peer_review_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    assigned_by TEXT,
                    due_date TEXT,
                    status TEXT DEFAULT 'assigned',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (submission_id) REFERENCES peer_review_submissions(submission_id)
                )
            ''')

            # ---- peer_review_feedback ----
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
                    FOREIGN KEY (assignment_id) REFERENCES hr_peer_review_assignments(assignment_id),
                    FOREIGN KEY (submission_id) REFERENCES peer_review_submissions(submission_id)
                )
            ''')

            # ---- peer_review_shared_resources ----
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

            # ---- peer_review_resource_ratings ----
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

            conn.commit()

        # Migrate any pre-existing peer_review_feedback whose FK still points
        # at the (colliding) academics `peer_review_assignments` table. Runs on
        # its own connection so PRAGMA foreign_keys can be toggled outside a
        # transaction. Idempotent: a no-op once the FK already references
        # hr_peer_review_assignments.
        _migrate_peer_review_feedback_fk()
    except sqlite3.Error as exc:
        print(f"Error initialising Staff HR academic schemas: {exc}")
        raise


def _migrate_peer_review_feedback_fk() -> None:
    """Rebuild legacy peer_review_feedback so its assignment FK references
    hr_peer_review_assignments instead of the colliding academics
    peer_review_assignments table. Idempotent and safe to call repeatedly."""
    conn = get_connection(row_factory=False)
    try:
        conn.isolation_level = None  # autocommit; we manage the transaction
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='peer_review_feedback'"
        ).fetchone()
        if not row or not row[0] or 'REFERENCES peer_review_assignments' not in row[0]:
            return  # fresh/correct schema — nothing to migrate

        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN")
        conn.execute("ALTER TABLE peer_review_feedback RENAME TO peer_review_feedback_legacy")
        conn.execute('''
            CREATE TABLE peer_review_feedback (
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
                FOREIGN KEY (assignment_id) REFERENCES hr_peer_review_assignments(assignment_id),
                FOREIGN KEY (submission_id) REFERENCES peer_review_submissions(submission_id)
            )
        ''')
        conn.execute("INSERT INTO peer_review_feedback SELECT * FROM peer_review_feedback_legacy")
        conn.execute("DROP TABLE peer_review_feedback_legacy")
        conn.execute("COMMIT")
        conn.execute("PRAGMA foreign_keys=ON")
    finally:
        conn.close()


def get_program_types():
    """Get list of supervision program types."""
    return ['phd', 'mphil', 'masters', 'undergraduate', 'postdoc']


def get_observation_types():
    """Get list of peer observation types."""
    return ['formal', 'informal', 'peer', 'developmental', 'probationary']
