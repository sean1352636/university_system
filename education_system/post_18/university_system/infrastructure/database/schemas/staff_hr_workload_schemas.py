"""Staff HR schemas — Workload & scheduling (schedules, teaching load, cover, workload norms).

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


def _init_workload_schemas() -> None:
    """Create every workload-domain Staff HR table."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # ---- staff_workload ----
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

            # ---- staff_schedules ----
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

            # ---- staff_workload ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_workload_user ON staff_workload(user_id)')

            # ---- faculty_schedule_blocks ----
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

            # ---- faculty_schedule_templates ----
            # `user_id` owns the template (FacultyScheduleManager writes it and
            # filters get_templates on it); `updated_at` is stamped on save.
            # The legacy `created_by` column is retained but nullable because
            # the manager no longer populates it.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS faculty_schedule_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_by TEXT,
                    blocks_json TEXT NOT NULL,
                    is_shared INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT
                )
            ''')

            # ---- schema-drift migration: faculty_schedule_templates ----
            # Older databases have the pre-refactor shape
            # (template_id, name, description, created_by NOT NULL,
            #  blocks_json, is_shared, created_at). FacultyScheduleManager
            # now writes `user_id` + `updated_at` and omits `created_by`.
            # Add the two missing columns and relax `created_by`'s NOT NULL
            # so save_as_template succeeds. Idempotent + row-preserving.
            try:
                safe_alter_table_add_column(
                    'faculty_schedule_templates', 'user_id', 'TEXT', conn
                )
            except Exception:
                pass
            try:
                safe_alter_table_add_column(
                    'faculty_schedule_templates', 'updated_at', 'TEXT', conn
                )
            except Exception:
                pass
            try:
                _tmpl_cols = {
                    row[1]: row for row in cursor.execute(
                        'PRAGMA table_info(faculty_schedule_templates)'
                    ).fetchall()
                }
                # row = (cid, name, type, notnull, dflt_value, pk)
                _created_by = _tmpl_cols.get('created_by')
                if _created_by is not None and _created_by[3] == 1:
                    # Rebuild to drop the legacy NOT NULL on created_by.
                    cursor.execute('DROP TABLE IF EXISTS faculty_schedule_templates__new')
                    cursor.execute('''
                        CREATE TABLE faculty_schedule_templates__new (
                            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id TEXT,
                            name TEXT NOT NULL,
                            description TEXT,
                            created_by TEXT,
                            blocks_json TEXT NOT NULL,
                            is_shared INTEGER DEFAULT 0,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            updated_at TEXT
                        )
                    ''')
                    cursor.execute('''
                        INSERT INTO faculty_schedule_templates__new (
                            template_id, user_id, name, description,
                            created_by, blocks_json, is_shared,
                            created_at, updated_at
                        )
                        SELECT template_id, user_id, name, description,
                               created_by, blocks_json, is_shared,
                               created_at, updated_at
                        FROM faculty_schedule_templates
                    ''')
                    cursor.execute('DROP TABLE faculty_schedule_templates')
                    cursor.execute(
                        'ALTER TABLE faculty_schedule_templates__new '
                        'RENAME TO faculty_schedule_templates'
                    )
            except sqlite3.Error:
                pass

            # ---- schedule_activity_types ----
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

            # ---- teaching_qualifications ----
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

            # ---- cover_skills ----
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

            # ---- cover_requests ----
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

            # ---- cover_offers ----
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

            # ---- cover_assignments ----
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

            # ---- workload_norms ----
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

            # ---- workload_allocations ----
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

            # ---- teaching_load_courses ----
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

            # ---- teaching_load_release_time ----
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

            # ---- teaching_load_standards ----
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

            # ---- teaching_load_history ----
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

            # NOTE: default grant_budget_categories and comm_hub_forums are
            # seeded by their OWNING modules (_init_finance_schemas /
            # _init_governance_schemas) so they run after those tables are
            # created. Seeding them here crashed a fresh DB because finance and
            # governance init run AFTER workload.

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

            conn.commit()
    except sqlite3.Error as exc:
        print(f"Error initialising Staff HR workload schemas: {exc}")
        raise
