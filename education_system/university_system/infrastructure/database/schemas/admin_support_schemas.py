from __future__ import annotations
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.university_system.core.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_course_evaluation_system_db():
    """Initialize the Course Evaluation System database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Course Evaluation System"))

        # Evaluation templates
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            template_type TEXT NOT NULL,
            description TEXT,
            is_default BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Evaluation questions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_questions (
            question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT NOT NULL,
            question_category TEXT NOT NULL,
            is_required BOOLEAN DEFAULT 1,
            scale_min INTEGER,
            scale_max INTEGER,
            options TEXT,
            display_order INTEGER,
            FOREIGN KEY (template_id) REFERENCES evaluation_templates (template_id)
        )
        ''')

        # Course evaluations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_evaluations (
            evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            semester TEXT NOT NULL,
            instructor_id TEXT NOT NULL,
            template_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            is_anonymous BOOLEAN DEFAULT 1,
            is_active BOOLEAN DEFAULT 1,
            response_count INTEGER DEFAULT 0,
            completion_rate REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (template_id) REFERENCES evaluation_templates (template_id)
        )
        ''')

        # Evaluation responses
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_responses (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_id INTEGER NOT NULL,
            student_id TEXT,
            response_date TEXT DEFAULT CURRENT_TIMESTAMP,
            is_complete BOOLEAN DEFAULT 0,
            time_taken_minutes INTEGER,
            FOREIGN KEY (evaluation_id) REFERENCES course_evaluations (evaluation_id)
        )
        ''')

        # Response answers
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_answers (
            answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            response_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            answer_value TEXT,
            numeric_value REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (response_id) REFERENCES evaluation_responses (response_id),
            FOREIGN KEY (question_id) REFERENCES evaluation_questions (question_id)
        )
        ''')

        # Evaluation results/analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_results (
            result_id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            average_score REAL,
            median_score REAL,
            mode_score REAL,
            standard_deviation REAL,
            response_count INTEGER,
            percentile_25 REAL,
            percentile_75 REAL,
            calculated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (evaluation_id) REFERENCES course_evaluations (evaluation_id),
            FOREIGN KEY (question_id) REFERENCES evaluation_questions (question_id)
        )
        ''')

        # Instructor performance tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS instructor_performance_history (
            performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            instructor_id TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            semester TEXT NOT NULL,
            avg_overall_rating REAL,
            avg_teaching_effectiveness REAL,
            avg_course_organization REAL,
            avg_student_engagement REAL,
            total_evaluations INTEGER,
            total_responses INTEGER,
            calculated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Course Evaluation System"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Course Evaluation", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# BUSINESS INTELLIGENCE REPORTS SCHEMAS
# ============================================================================


def init_auth_tables():
    """Initialize auth system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="auth"))

        # Create login_attempts table
        cursor.execute('''
        CREATE TABLE login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    attempt_time TEXT NOT NULL,
                    ip_address TEXT,
                    success INTEGER NOT NULL
                )
        ''')

        # Create permissions table
        cursor.execute('''
        CREATE TABLE permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    permission_name TEXT UNIQUE NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
        ''')

        # Create photo_permissions table
        cursor.execute('''
        CREATE TABLE photo_permissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        permission_type TEXT,
                        consent_given BOOLEAN DEFAULT 0,
                        conditions TEXT,
                        valid_from TEXT,
                        valid_until TEXT,
                        parent_signature TEXT,
                        date_signed TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create role_permissions table
        cursor.execute('''
        CREATE TABLE role_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role_id INTEGER NOT NULL,
                    permission_id INTEGER NOT NULL,
                    FOREIGN KEY (role_id) REFERENCES roles (id),
                    FOREIGN KEY (permission_id) REFERENCES permissions (id),
                    UNIQUE(role_id, permission_id)
                )
        ''')

        # Create roles table
        cursor.execute('''
        CREATE TABLE roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role_name TEXT UNIQUE NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
        ''')

        # Create security_settings table
        cursor.execute('''
        CREATE TABLE security_settings (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            setting_name TEXT UNIQUE,
                            setting_value TEXT,
                            updated_at TEXT,
                            updated_by TEXT
                        )
        ''')

        # Create two_fa_recovery_codes table
        cursor.execute('''
        CREATE TABLE two_fa_recovery_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    code_hash TEXT NOT NULL,
                    is_used INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    used_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
        ''')

        # Create user_accounts table
        cursor.execute('''
        CREATE TABLE user_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    last_login TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    password_reset_required INTEGER DEFAULT 0,
                    two_fa_enabled INTEGER DEFAULT 0,
                    two_fa_secret TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
        ''')

        # Create user_achievements table
        cursor.execute('''
        CREATE TABLE user_achievements (
                    achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    achievement_type TEXT NOT NULL,
                    achievement_name TEXT NOT NULL,
                    description TEXT,
                    earned_date TEXT NOT NULL,
                    points INTEGER DEFAULT 0
                )
        ''')

        # Create user_permissions table
        cursor.execute('''
        CREATE TABLE user_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    permission_id INTEGER NOT NULL,
                    granted INTEGER NOT NULL,
                    UNIQUE(user_id, permission_id),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(permission_id) REFERENCES permissions(id) ON DELETE CASCADE
                )
        ''')

        # Create user_preferences table
        cursor.execute('''
        CREATE TABLE user_preferences (
                    user_id TEXT PRIMARY KEY,
                    email_notifications BOOLEAN DEFAULT 1,
                    in_app_notifications BOOLEAN DEFAULT 1,
                    push_notifications BOOLEAN DEFAULT 1,
                    digest_frequency TEXT DEFAULT 'daily',  -- immediate, daily, weekly
                    theme TEXT DEFAULT 'light',
                    language TEXT DEFAULT 'en',
                    timezone TEXT DEFAULT 'UTC',
                    preferences_json TEXT  -- Additional JSON preferences
                )
        ''')

        # Create user_timezone_preferences table
        cursor.execute('''
        CREATE TABLE user_timezone_preferences (
                            user_id TEXT PRIMARY KEY,
                            timezone_name TEXT NOT NULL,
                            auto_dst BOOLEAN DEFAULT TRUE,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            FOREIGN KEY (user_id) REFERENCES users (id)
                        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="auth"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="auth", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# CAREER TABLES (7 tables)
# ============================================================================


def init_audit_tables():
    """Initialize audit system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="audit"))

        # Create audit_log table
        cursor.execute('''
        CREATE TABLE audit_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    action TEXT NOT NULL,
                    table_name TEXT,
                    record_id TEXT,
                    old_values TEXT, -- JSON
                    new_values TEXT, -- JSON
                    ip_address TEXT,
                    user_agent TEXT,
                    session_id TEXT,
                    timestamp TEXT NOT NULL
                , accommodation_id INTEGER, details TEXT)
        ''')

        # Create audit_trail table
        cursor.execute('''
        CREATE TABLE audit_trail (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    old_values TEXT,  -- JSON
                    new_values TEXT,  -- JSON
                    ip_address TEXT,
                    user_agent TEXT,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    duration REAL,
                    timestamp TEXT NOT NULL
                )
        ''')

        # Create backup_history table
        cursor.execute('''
        CREATE TABLE backup_history (
                            id TEXT PRIMARY KEY,
                            backup_type TEXT NOT NULL,
                            file_path TEXT NOT NULL,
                            file_size INTEGER,
                            backup_time TEXT NOT NULL,
                            status TEXT NOT NULL,
                            notes TEXT
                        )
        ''')

        # Create backups table
        cursor.execute('''
        CREATE TABLE backups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        backup_name TEXT,
                        backup_path TEXT,
                        backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        backup_size INTEGER,
                        description TEXT
                    )
        ''')

        # Create privacy_audit_log table
        cursor.execute('''
        CREATE TABLE privacy_audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        action TEXT NOT NULL,
                        student_id TEXT,
                        user_id INTEGER,
                        data_accessed TEXT,
                        timestamp TEXT NOT NULL,
                        ip_address TEXT
                    )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="audit"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="audit", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# AUTH TABLES (12 tables)
# ============================================================================


def init_documents_tables():
    """Initialize documents system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="documents"))

        # Create document_repository table
        cursor.execute('''
        CREATE TABLE document_repository (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            title TEXT NOT NULL CHECK(length(title) > 0),
                            content TEXT NOT NULL CHECK(length(content) > 0),
                            content_hash TEXT NOT NULL,
                            author_id INTEGER NOT NULL,
                            module_code TEXT,
                            submission_date TEXT NOT NULL,
                            file_type TEXT,
                            word_count INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (author_id) REFERENCES users (id) ON DELETE CASCADE,
                            FOREIGN KEY (module_code) REFERENCES modules (module_code) ON DELETE SET NULL
                        )
        ''')

        # Create document_tags table
        cursor.execute('''
        CREATE TABLE document_tags (
                        tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tag_name TEXT UNIQUE,
                        tag_color TEXT,
                        description TEXT
                    )
        ''')

        # Create document_workflow table
        cursor.execute('''
        CREATE TABLE document_workflow (
                        workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id INTEGER,
                        step_name TEXT,
                        step_order INTEGER,
                        assigned_to TEXT,
                        status TEXT,
                        comments TEXT,
                        completed_date TEXT,
                        completed_by TEXT,
                        FOREIGN KEY (document_id) REFERENCES student_documents (document_id)
                    )
        ''')

        # Create response_templates table
        cursor.execute('''
        CREATE TABLE response_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    subject TEXT,
                    content TEXT NOT NULL,
                    category TEXT,
                    created_by TEXT NOT NULL,
                    created_datetime TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    usage_count INTEGER DEFAULT 0,
                    variables TEXT  -- JSON array of variable names
                )
        ''')

        # Create schedule_templates table
        cursor.execute('''
        CREATE TABLE schedule_templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_name TEXT UNIQUE,
                        description TEXT,
                        template_data TEXT,
                        created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT
                    )
        ''')

        # Create workflow_instances table
        cursor.execute('''
        CREATE TABLE workflow_instances (
                    instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id INTEGER NOT NULL,
                    entity_type TEXT NOT NULL, -- 'refund', 'payment_plan', 'scholarship', etc.
                    entity_id INTEGER NOT NULL,
                    current_step INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'pending', -- pending, in_progress, completed, cancelled
                    assigned_to TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    metadata TEXT, -- JSON with instance-specific data
                    FOREIGN KEY (workflow_id) REFERENCES workflows (workflow_id)
                )
        ''')

        # Create workflows table
        cursor.execute('''
        CREATE TABLE workflows (
                    workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_name TEXT NOT NULL,
                    workflow_type TEXT NOT NULL, -- 'approval', 'notification', 'automation'
                    trigger_conditions TEXT, -- JSON
                    workflow_steps TEXT, -- JSON with step definitions
                    is_active BOOLEAN DEFAULT 1,
                    created_by TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="documents"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="documents", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# FINANCE TABLES (18 tables)
# ============================================================================


def init_support_tables():
    """Initialize support system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="support"))

        # Create escalation_rules table
        cursor.execute('''
        CREATE TABLE escalation_rules (
                    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT,
                    priority TEXT,
                    condition_type TEXT NOT NULL,  -- time_based, status_based, keyword_based
                    condition_value TEXT NOT NULL,
                    action_type TEXT NOT NULL,  -- escalate, reassign, notify
                    action_target TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_by TEXT NOT NULL,
                    created_datetime TEXT NOT NULL
                )
        ''')

        # Create faqs table
        cursor.execute('''
        CREATE TABLE faqs (
                    faq_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    category TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_datetime TEXT NOT NULL,
                    updated_datetime TEXT,
                    view_count INTEGER DEFAULT 0,
                    helpful_votes INTEGER DEFAULT 0,
                    tags TEXT,  -- JSON array
                    is_featured BOOLEAN DEFAULT 0
                )
        ''')

        # Create peer_support_groups table
        cursor.execute('''
        CREATE TABLE peer_support_groups (
                    group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_name TEXT,
                    description TEXT,
                    support_type TEXT,
                    facilitator_id TEXT,
                    max_members INTEGER,
                    current_members INTEGER DEFAULT 0,
                    meeting_schedule TEXT,
                    status TEXT DEFAULT 'active',
                    created_date TEXT,
                    FOREIGN KEY (facilitator_id) REFERENCES students (student_id)
                )
        ''')

        # Create support_group_members table
        cursor.execute('''
        CREATE TABLE support_group_members (
                    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER,
                    student_id TEXT,
                    join_date TEXT,
                    anonymous_id TEXT,
                    status TEXT DEFAULT 'active',
                    FOREIGN KEY (group_id) REFERENCES peer_support_groups (group_id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create support_resources table
        cursor.execute('''
        CREATE TABLE support_resources (
                    resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    url TEXT,
                    file_path TEXT,
                    created_by TEXT NOT NULL,
                    created_datetime TEXT NOT NULL,
                    updated_datetime TEXT,
                    access_count INTEGER DEFAULT 0,
                    tags TEXT,  -- JSON array
                    content_type TEXT,
                    is_featured BOOLEAN DEFAULT 0,
                    requires_auth BOOLEAN DEFAULT 0
                )
        ''')

        # Create support_tickets table
        cursor.execute('''
        CREATE TABLE support_tickets (
                    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_datetime TEXT NOT NULL,
                    last_updated_datetime TEXT,
                    assigned_to TEXT,
                    escalated_at TEXT,
                    resolved_at TEXT,
                    closed_at TEXT,
                    estimated_resolution TEXT,
                    sentiment TEXT DEFAULT 'neutral',
                    satisfaction_rating INTEGER,
                    tags TEXT,  -- JSON array of tags
                    parent_ticket_id INTEGER, due_date TEXT, user_id INTEGER, subject TEXT DEFAULT 'No Subject', created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,  -- For merged tickets
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (parent_ticket_id) REFERENCES support_tickets (ticket_id)
                )
        ''')

        # Create ticket_attachments table
        cursor.execute('''
        CREATE TABLE ticket_attachments (
                    attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_type TEXT NOT NULL,
                    mime_type TEXT,
                    uploaded_by TEXT NOT NULL,
                    uploaded_datetime TEXT NOT NULL,
                    is_public BOOLEAN DEFAULT 0,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id)
                )
        ''')

        # Create ticket_audit_log table
        cursor.execute('''
        CREATE TABLE ticket_audit_log (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    user_id INTEGER,
                    action TEXT NOT NULL,
                    old_values TEXT,
                    new_values TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
        ''')

        # Create ticket_escalations table
        cursor.execute('''
        CREATE TABLE ticket_escalations (
                    escalation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    escalation_level INTEGER,
                    escalated_to INTEGER,
                    escalated_by INTEGER,
                    escalation_reason TEXT,
                    resolved BOOLEAN DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                    FOREIGN KEY (escalated_to) REFERENCES users (id),
                    FOREIGN KEY (escalated_by) REFERENCES users (id)
                )
        ''')

        # Create ticket_links table
        cursor.execute('''
        CREATE TABLE ticket_links (
                    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    linked_ticket_id INTEGER,
                    link_type TEXT,
                    created_by INTEGER,
                    created_at TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                    FOREIGN KEY (linked_ticket_id) REFERENCES support_tickets (ticket_id),
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
        ''')

        # Create ticket_replies table
        cursor.execute('''
        CREATE TABLE ticket_replies (
                    reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    user_id INTEGER,
                    message TEXT NOT NULL,
                    is_internal BOOLEAN DEFAULT 0,
                    reply_type TEXT DEFAULT 'comment',
                    time_spent REAL DEFAULT 0,
                    created_at TEXT,
                    edited_at TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
        ''')

        # Create ticket_responses table
        cursor.execute('''
        CREATE TABLE ticket_responses (
                    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    responder_id TEXT NOT NULL,
                    responder_role TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    response_datetime TEXT NOT NULL,
                    is_internal BOOLEAN DEFAULT 0,
                    is_auto_generated BOOLEAN DEFAULT 0,
                    template_used TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id)
                )
        ''')

        # Create ticket_templates table
        cursor.execute('''
        CREATE TABLE ticket_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    title_template TEXT NOT NULL,
                    description_template TEXT NOT NULL,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_datetime TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    usage_count INTEGER DEFAULT 0
                )
        ''')

        # Create ticket_time_tracking table
        cursor.execute('''
        CREATE TABLE ticket_time_tracking (
                    time_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    user_id INTEGER,
                    start_time TEXT,
                    end_time TEXT,
                    duration_minutes INTEGER,
                    description TEXT,
                    billable BOOLEAN DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
        ''')

        # Create ticket_workflows table
        cursor.execute('''
        CREATE TABLE ticket_workflows (
                    workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    trigger_type TEXT NOT NULL,
                    trigger_conditions TEXT,
                    actions TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_by INTEGER,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="support"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="support", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# TRAVEL TABLES (5 tables)
# ============================================================================


def init_parent_tables():
    """Initialize parent system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="parent"))

        # Create parent_documents table
        cursor.execute('''
        CREATE TABLE parent_documents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        parent_id TEXT,
                        student_id TEXT,
                        document_type TEXT,
                        document_name TEXT,
                        file_path TEXT,
                        upload_date TEXT,
                        status TEXT DEFAULT 'pending',
                        expiry_date TEXT,
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create parent_messages table
        cursor.execute('''
        CREATE TABLE parent_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        parent_id TEXT,
                        teacher_id INTEGER,
                        student_id TEXT,
                        message_content TEXT,
                        created_date TEXT,
                        is_read BOOLEAN DEFAULT 0,
                        is_from_parent BOOLEAN DEFAULT 1,
                        message_type TEXT DEFAULT 'individual',
                        group_id TEXT,
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                        FOREIGN KEY (teacher_id) REFERENCES users (id),
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create parent_preferences table
        cursor.execute('''
        CREATE TABLE parent_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id TEXT UNIQUE,
                    email_notifications BOOLEAN DEFAULT 1,
                    sms_notifications BOOLEAN DEFAULT 0,
                    grade_alerts BOOLEAN DEFAULT 1,
                    attendance_alerts BOOLEAN DEFAULT 1,
                    behavior_alerts BOOLEAN DEFAULT 1,
                    assignment_alerts BOOLEAN DEFAULT 0,
                    weekly_summary BOOLEAN DEFAULT 1,
                    notification_timing TEXT DEFAULT '08:00',
                    quiet_hours_start TEXT DEFAULT '20:00',
                    quiet_hours_end TEXT DEFAULT '07:00',
                    FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
                )
        ''')

        # Create parent_teacher_meetings table
        cursor.execute('''
        CREATE TABLE parent_teacher_meetings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        parent_id TEXT,
                        teacher_id INTEGER,
                        student_id TEXT,
                        meeting_date TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        location TEXT,
                        meeting_type TEXT,
                        status TEXT DEFAULT 'scheduled',
                        agenda TEXT,
                        notes TEXT,
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                        FOREIGN KEY (teacher_id) REFERENCES users (id),
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create parent_user_mapping table
        cursor.execute('''
        CREATE TABLE parent_user_mapping (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    parent_id TEXT UNIQUE,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
                )
        ''')

        # Create pickup_authorizations table
        cursor.execute('''
        CREATE TABLE pickup_authorizations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        authorized_person_name TEXT,
                        relationship TEXT,
                        phone_number TEXT,
                        id_number TEXT,
                        photo_path TEXT,
                        valid_from TEXT,
                        valid_until TEXT,
                        active BOOLEAN DEFAULT 1,
                        created_by TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="parent"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="parent", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# PARKING TABLES (1 tables)
# ============================================================================


def init_library_tables():
    """Initialize library system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="library"))

        # Create book_loans table
        cursor.execute('''
        CREATE TABLE book_loans (
                    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    checkout_date TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    return_date TEXT,
                    status TEXT DEFAULT 'active',
                    fine_amount REAL DEFAULT 0.0,
                    renewal_count INTEGER DEFAULT 0,
                    reading_progress INTEGER DEFAULT 0,
                    checkout_method TEXT DEFAULT 'manual',
                    staff_id TEXT,
                    notes TEXT
                )
        ''')

        # Create book_recommendations table
        cursor.execute('''
        CREATE TABLE book_recommendations (
                    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    book_id TEXT NOT NULL,
                    recommendation_type TEXT NOT NULL,
                    confidence_score REAL DEFAULT 0.0,
                    generated_date TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    clicked BOOLEAN DEFAULT FALSE
                )
        ''')

        # Create book_requests table
        cursor.execute('''
        CREATE TABLE book_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    isbn TEXT,
                    reason TEXT,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 1,
                    requested_date TEXT NOT NULL,
                    processed_date TEXT,
                    processed_by TEXT,
                    notes TEXT
                )
        ''')

        # Create book_reservations table
        cursor.execute('''
        CREATE TABLE book_reservations (
                    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    reservation_date TEXT NOT NULL,
                    expiry_date TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    priority_order INTEGER DEFAULT 1,
                    notification_sent BOOLEAN DEFAULT FALSE
                )
        ''')

        # Create book_reviews table
        cursor.execute('''
        CREATE TABLE book_reviews (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                    review_text TEXT,
                    review_date TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    helpful_votes INTEGER DEFAULT 0,
                    moderated_by TEXT,
                    moderation_date TEXT
                )
        ''')

        # Create books table
        cursor.execute('''
        CREATE TABLE books (
                    book_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    isbn TEXT UNIQUE,
                    publisher TEXT,
                    category TEXT,
                    year_published INTEGER,
                    description TEXT,
                    location TEXT,
                    status TEXT DEFAULT 'available',
                    added_date TEXT,
                    last_updated TEXT,
                    reading_level TEXT,
                    tags TEXT,
                    cover_image_path TEXT,
                    digital_copy_path TEXT,
                    acquisition_cost REAL DEFAULT 0.0,
                    barcode TEXT UNIQUE,
                    qr_code_path TEXT,
                    total_pages INTEGER,
                    language TEXT DEFAULT 'English',
                    edition TEXT,
                    condition_notes TEXT
                )
        ''')

        # Create digital_library table
        cursor.execute('''
        CREATE TABLE digital_library (
                    digital_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER,
                    category TEXT,
                    description TEXT,
                    access_level TEXT DEFAULT 'public',
                    download_count INTEGER DEFAULT 0,
                    added_date TEXT NOT NULL
                )
        ''')

        # Create interlibrary_loans table
        cursor.execute('''
        CREATE TABLE interlibrary_loans (
                    ill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    isbn TEXT,
                    source_library TEXT,
                    request_date TEXT NOT NULL,
                    expected_arrival TEXT,
                    actual_arrival TEXT,
                    due_date TEXT,
                    return_date TEXT,
                    status TEXT DEFAULT 'requested',
                    cost REAL DEFAULT 0.0
                )
        ''')

        # Create library_accounts table
        cursor.execute('''
        CREATE TABLE library_accounts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        book_title TEXT,
                        author TEXT,
                        isbn TEXT,
                        checkout_date TEXT,
                        due_date TEXT,
                        return_date TEXT,
                        fine_amount DECIMAL(10,2) DEFAULT 0.00,
                        status TEXT DEFAULT 'checked_out',
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create library_settings table
        cursor.execute('''
        CREATE TABLE library_settings (
                        setting_name TEXT PRIMARY KEY,
                        setting_value TEXT NOT NULL,
                        description TEXT,
                        setting_type TEXT DEFAULT 'string',
                        min_value REAL,
                        max_value REAL,
                        allowed_values TEXT
                    )
        ''')

        # Create reading_goals table
        cursor.execute('''
        CREATE TABLE reading_goals (
                    goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    goal_type TEXT NOT NULL,
                    target_value INTEGER NOT NULL,
                    current_value INTEGER DEFAULT 0,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_date TEXT NOT NULL
                )
        ''')

        # Create reading_list_items table
        cursor.execute('''
        CREATE TABLE reading_list_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_id INTEGER NOT NULL,
                    book_id TEXT NOT NULL,
                    added_date TEXT NOT NULL,
                    added_by TEXT NOT NULL,
                    notes TEXT,
                    order_index INTEGER DEFAULT 0
                )
        ''')

        # Create reading_lists table
        cursor.execute('''
        CREATE TABLE reading_lists (
                    list_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    creator_id TEXT NOT NULL,
                    created_date TEXT NOT NULL,
                    is_public BOOLEAN DEFAULT FALSE,
                    is_collaborative BOOLEAN DEFAULT FALSE,
                    category TEXT,
                    target_reading_level TEXT
                )
        ''')

        # Create resource_bookings table
        cursor.execute('''
        CREATE TABLE resource_bookings (
                            id TEXT PRIMARY KEY,
                            resource_id TEXT NOT NULL,
                            event_id TEXT,
                            start_time TEXT NOT NULL,
                            end_time TEXT NOT NULL,
                            status TEXT DEFAULT 'confirmed',
                            notes TEXT,
                            date_added TEXT NOT NULL,
                            FOREIGN KEY (resource_id) REFERENCES resources (id) ON DELETE CASCADE,
                            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
                        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="library"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="library", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# OTHER TABLES (58 tables)
# ============================================================================


def init_commerce_tables():
    """Initialize commerce system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="commerce"))

        # Create inventory table
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

        # Create meal_accounts table
        cursor.execute('''
        CREATE TABLE meal_accounts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT UNIQUE,
                        balance DECIMAL(10,2) DEFAULT 0.00,
                        low_balance_threshold DECIMAL(10,2) DEFAULT 10.00,
                        auto_topup_enabled BOOLEAN DEFAULT 0,
                        auto_topup_amount DECIMAL(10,2) DEFAULT 20.00,
                        last_updated TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create menu_items table
        cursor.execute('''
        CREATE TABLE menu_items (
                        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        price REAL NOT NULL,
                        category TEXT,
                        allergens TEXT,
                        vegetarian BOOLEAN DEFAULT 0,
                        vegan BOOLEAN DEFAULT 0,
                        available BOOLEAN DEFAULT 1
                    )
        ''')

        # Create restaurant_customers table
        cursor.execute('''
        CREATE TABLE restaurant_customers (
                        customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        email TEXT,
                        phone TEXT,
                        loyalty_tier TEXT DEFAULT 'Bronze',
                        loyalty_points INTEGER DEFAULT 0,
                        total_spent REAL DEFAULT 0
                    )
        ''')

        # Create restaurant_inventory table
        cursor.execute('''
        CREATE TABLE restaurant_inventory (
                        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        quantity REAL DEFAULT 0,
                        unit TEXT,
                        cost_per_unit REAL,
                        reorder_level REAL DEFAULT 0
                    )
        ''')

        # Create restaurant_orders table
        cursor.execute('''
        CREATE TABLE restaurant_orders (
                        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id INTEGER,
                        order_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                        total_price REAL,
                        tax_amount REAL,
                        status TEXT DEFAULT 'Pending',
                        payment_method TEXT
                    )
        ''')

        # Create restaurant_staff table
        cursor.execute('''
        CREATE TABLE restaurant_staff (
                        staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        role TEXT NOT NULL,
                        hourly_rate REAL,
                        status TEXT DEFAULT 'Active',
                        performance_score REAL
                    )
        ''')

        # Create restaurant_tables table
        cursor.execute('''
        CREATE TABLE restaurant_tables (
                        table_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        capacity INTEGER NOT NULL,
                        status TEXT DEFAULT 'Available',
                        location TEXT,
                        table_type TEXT DEFAULT 'Standard'
                    )
        ''')

        # Create shop_cart table
        cursor.execute('''
        CREATE TABLE shop_cart (
                    cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    added_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (product_id) REFERENCES shop_products (product_id),
                    UNIQUE(user_id, product_id)
                )
        ''')

        # Create shop_discounts table
        cursor.execute('''
        CREATE TABLE shop_discounts (
                    discount_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    discount_type TEXT NOT NULL,
                    discount_value REAL NOT NULL,
                    start_date TEXT,
                    end_date TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    applicable_products TEXT,
                    min_purchase_amount REAL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
        ''')

        # Create shop_inventory table
        cursor.execute('''
        CREATE TABLE shop_inventory (
                    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    last_restock_date TEXT,
                    restock_threshold INTEGER DEFAULT 5,
                    FOREIGN KEY (product_id) REFERENCES shop_products (product_id)
                )
        ''')

        # Create shop_products table
        cursor.execute('''
        CREATE TABLE shop_products (
                    product_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    category TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    tax_rate REAL DEFAULT 0.2,
                    is_active BOOLEAN DEFAULT 1
                )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="commerce"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="commerce", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# COMMUNICATION TABLES (15 tables)
# ============================================================================


def init_other_tables():
    """Initialize other system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="other"))

        # Create academic_goals table
        cursor.execute('''
        CREATE TABLE academic_goals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        parent_id TEXT,
                        goal_title TEXT,
                        description TEXT,
                        target_grade TEXT,
                        target_date TEXT,
                        current_progress TEXT,
                        status TEXT DEFAULT 'active',
                        created_date TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id),
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
                    )
        ''')

        # Create academic_years table
        cursor.execute('''
        CREATE TABLE academic_years (
                            id TEXT PRIMARY KEY,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL,
                            date_added TEXT NOT NULL,
                            CONSTRAINT valid_dates CHECK (start_date < end_date)
                        )
        ''')

        # Create achievement_badges table
        cursor.execute('''
        CREATE TABLE achievement_badges (
                    badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    badge_name TEXT,
                    badge_description TEXT,
                    points_required INTEGER,
                    badge_icon TEXT,
                    category TEXT
                )
        ''')

        # Create advanced_detection_results table
        cursor.execute('''
        CREATE TABLE advanced_detection_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        submission_id INTEGER NOT NULL,
                        temporal_analysis TEXT,
                        citation_analysis TEXT,
                        behavioral_analysis TEXT,
                        multimodal_analysis TEXT,
                        adversarial_analysis TEXT,
                        ensemble_prediction TEXT,
                        risk_prediction TEXT,
                        bias_adjusted_score REAL,
                        blockchain_hash TEXT,
                        FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
                    )
        ''')

        # Create allergies table
        cursor.execute('''
        CREATE TABLE allergies (
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

        # Create assessment_competencies table
        cursor.execute('''
        CREATE TABLE assessment_competencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assessment_id INTEGER NOT NULL,
                    competency_id INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id),
                    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id)
                )
        ''')

        # Create assessment_outcomes table
        cursor.execute('''
        CREATE TABLE assessment_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assessment_id INTEGER NOT NULL,
                    outcome_id INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id),
                    FOREIGN KEY (outcome_id) REFERENCES learning_outcomes(outcome_id)
                )
        ''')

        # Create assessments table
        cursor.execute('''
        CREATE TABLE assessments (
                    assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assessment_name TEXT NOT NULL,
                    assessment_type TEXT NOT NULL,
                    module_code TEXT NOT NULL,
                    max_points REAL NOT NULL,
                    weight REAL NOT NULL,
                    due_date TEXT,
                    date_created TEXT DEFAULT (datetime('now')),
                    description TEXT,
                    rubric TEXT,
                    FOREIGN KEY (module_code) REFERENCES modules (module_code)
                )
        ''')

        # Create business_directory table
        cursor.execute('''
        CREATE TABLE business_directory (
                    business_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alumni_id TEXT,
                    business_name TEXT,
                    business_description TEXT,
                    industry TEXT,
                    website TEXT,
                    contact_email TEXT,
                    services_offered TEXT,
                    location TEXT,
                    created_date TEXT,
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create care_plans table
        cursor.execute('''
        CREATE TABLE care_plans (
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

        # Create collection_agencies table
        cursor.execute('''
        CREATE TABLE collection_agencies (
                    agency_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agency_name TEXT NOT NULL,
                    contact_email TEXT,
                    contact_phone TEXT,
                    commission_rate DECIMAL(5,2),
                    minimum_amount DECIMAL(10,2),
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create collection_cases table
        cursor.execute('''
        CREATE TABLE collection_cases (
                    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    agency_id INTEGER,
                    total_debt DECIMAL(10,2) NOT NULL,
                    case_status TEXT DEFAULT 'new', -- new, assigned, in_progress, resolved, closed
                    assigned_date TEXT,
                    resolution_date TEXT,
                    amount_collected DECIMAL(10,2) DEFAULT 0,
                    commission_paid DECIMAL(10,2) DEFAULT 0,
                    notes TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (agency_id) REFERENCES collection_agencies (agency_id)
                )
        ''')

        # Create competencies table
        cursor.execute('''
        CREATE TABLE competencies (
                    competency_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT
                )
        ''')

        # Create competency_levels table
        cursor.execute('''
        CREATE TABLE competency_levels (
                    level_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competency_id INTEGER NOT NULL,
                    level_name TEXT NOT NULL,
                    level_value INTEGER NOT NULL,
                    description TEXT,
                    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id)
                )
        ''')

        # Create competition_participants table
        cursor.execute('''
        CREATE TABLE competition_participants (
                    participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competition_id INTEGER,
                    club_id INTEGER,
                    student_id TEXT,
                    registration_date TEXT,
                    score REAL DEFAULT 0.0,
                    rank_position INTEGER,
                    FOREIGN KEY (competition_id) REFERENCES club_competitions (competition_id),
                    FOREIGN KEY (club_id) REFERENCES student_clubs (club_id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create currency_settings table
        cursor.execute('''
        CREATE TABLE currency_settings (
                    setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    base_currency TEXT DEFAULT 'GBP',
                    auto_update_rates BOOLEAN DEFAULT 1,
                    rate_update_frequency INTEGER DEFAULT 24, -- hours
                    last_rate_update TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create data_retention table
        cursor.execute('''
        CREATE TABLE data_retention (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        data_type TEXT NOT NULL,
                        retention_period INTEGER NOT NULL,
                        deletion_date TEXT,
                        status TEXT DEFAULT 'active'
                    )
        ''')

        # Create data_retention_policies table
        cursor.execute('''
        CREATE TABLE data_retention_policies (
                    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_type TEXT NOT NULL,
                    retention_period_months INTEGER NOT NULL,
                    deletion_method TEXT DEFAULT 'soft', -- 'soft', 'hard', 'anonymize'
                    last_cleanup_date TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create donor_recognition table
        cursor.execute('''
        CREATE TABLE donor_recognition (
                    recognition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alumni_id TEXT,
                    recognition_level TEXT,
                    total_donated REAL,
                    recognition_date TEXT,
                    benefits TEXT,
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create emergency_contacts table
        cursor.execute('''
        CREATE TABLE emergency_contacts (
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

        # Create engagement_points table
        cursor.execute('''
        CREATE TABLE engagement_points (
                    point_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alumni_id TEXT,
                    activity_type TEXT,
                    points_earned INTEGER,
                    activity_date TEXT,
                    description TEXT,
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create equipment_checkouts table
        cursor.execute('''
        CREATE TABLE equipment_checkouts (
                    checkout_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_id INTEGER,
                    borrower_id TEXT,
                    club_id INTEGER,
                    checkout_date TEXT,
                    expected_return TEXT,
                    actual_return TEXT,
                    condition_out TEXT,
                    condition_in TEXT,
                    notes TEXT,
                    status TEXT DEFAULT 'checked_out',
                    FOREIGN KEY (equipment_id) REFERENCES union_equipment (equipment_id),
                    FOREIGN KEY (borrower_id) REFERENCES students (student_id),
                    FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
                )
        ''')

        # Create exchange_rates table
        cursor.execute('''
        CREATE TABLE exchange_rates (
                    rate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_currency TEXT NOT NULL,
                    to_currency TEXT NOT NULL,
                    exchange_rate DECIMAL(10,6) NOT NULL,
                    rate_date TEXT NOT NULL,
                    source TEXT, -- 'manual', 'api', 'bank'
                    created_at TEXT
                )
        ''')

        # Create extension_requests table
        cursor.execute('''
        CREATE TABLE extension_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    requested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    new_due_date TIMESTAMP NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    reviewed_by INTEGER,
                    reviewed_date TIMESTAMP,
                    review_comments TEXT,
                    FOREIGN KEY (assignment_id) REFERENCES assignments (id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (reviewed_by) REFERENCES users (id)
                )
        ''')

        # Create extracurricular_activities table
        cursor.execute('''
        CREATE TABLE extracurricular_activities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        activity_name TEXT,
                        description TEXT,
                        supervisor TEXT,
                        meeting_schedule TEXT,
                        location TEXT,
                        max_participants INTEGER,
                        fee DECIMAL(10,2) DEFAULT 0.00,
                        status TEXT DEFAULT 'active'
                    )
        ''')

        # Create graduation_requirements table
        cursor.execute('''
        CREATE TABLE graduation_requirements (
                            id TEXT PRIMARY KEY,
                            requirement_name TEXT NOT NULL,
                            requirement_type TEXT NOT NULL,
                            credits_required INTEGER,
                            course_category TEXT,
                            deadline_date TEXT,
                            is_mandatory BOOLEAN DEFAULT TRUE,
                            created_at TEXT NOT NULL
                        )
        ''')

        # Create holiday_calendars table
        cursor.execute('''
        CREATE TABLE holiday_calendars (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            country_code TEXT NOT NULL,
                            region TEXT,
                            is_active BOOLEAN DEFAULT TRUE,
                            date_added TEXT NOT NULL
                        )
        ''')

        # Create holidays table
        cursor.execute('''
        CREATE TABLE holidays (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        holiday_name TEXT,
                        start_date DATE,
                        end_date DATE,
                        description TEXT,
                        recurring BOOLEAN DEFAULT 0
                    )
        ''')

        # Create institutions table
        cursor.execute('''
        CREATE TABLE institutions (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        type TEXT,
                        country TEXT,
                        created_at TEXT NOT NULL
                    )
        ''')

        # Create intervention_types table
        cursor.execute('''
        CREATE TABLE intervention_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    description TEXT
                )
        ''')

        # Create kb_articles table
        cursor.execute('''
        CREATE TABLE kb_articles (
                    article_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT,
                    category TEXT NOT NULL,
                    tags TEXT,  -- JSON array
                    author_id TEXT NOT NULL,
                    created_datetime TEXT NOT NULL,
                    updated_datetime TEXT,
                    published_datetime TEXT,
                    is_published BOOLEAN DEFAULT 0,
                    view_count INTEGER DEFAULT 0,
                    helpful_votes INTEGER DEFAULT 0,
                    not_helpful_votes INTEGER DEFAULT 0,
                    search_keywords TEXT,  -- Space-separated keywords for search
                    related_articles TEXT  -- JSON array of related article IDs
                )
        ''')

        # Create knowledge_base table
        cursor.execute('''
        CREATE TABLE knowledge_base (
                    article_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT,
                    tags TEXT,
                    author_id INTEGER,
                    status TEXT DEFAULT 'draft',
                    views INTEGER DEFAULT 0,
                    helpful_votes INTEGER DEFAULT 0,
                    unhelpful_votes INTEGER DEFAULT 0,
                    search_keywords TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (author_id) REFERENCES users (id)
                )
        ''')

        # Create learning_outcomes table
        cursor.execute('''
        CREATE TABLE learning_outcomes (
                    outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    outcome_code TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT,
                    level INTEGER
                )
        ''')

        # Create networking_connections table
        cursor.execute('''
        CREATE TABLE networking_connections (
                    connection_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    requester_id TEXT,
                    recipient_id TEXT,
                    connection_date TEXT,
                    status TEXT DEFAULT 'pending',
                    message TEXT,
                    FOREIGN KEY (requester_id) REFERENCES alumni (alumni_id),
                    FOREIGN KEY (recipient_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create newsletters table
        cursor.execute('''
        CREATE TABLE newsletters (
                    newsletter_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    content TEXT,
                    template_id INTEGER,
                    target_audience TEXT,
                    send_date TEXT,
                    created_date TEXT,
                    created_by TEXT,
                    status TEXT DEFAULT 'draft',
                    open_rate REAL DEFAULT 0.0,
                    click_rate REAL DEFAULT 0.0
                )
        ''')

        # Create outcome_results table
        cursor.execute('''
        CREATE TABLE outcome_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    outcome_id INTEGER NOT NULL,
                    achievement_level REAL,
                    assessment_date TEXT,
                    evidence TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(student_id),
                    FOREIGN KEY (outcome_id) REFERENCES learning_outcomes(outcome_id)
                )
        ''')

        # Create photo_gallery table
        cursor.execute('''
        CREATE TABLE photo_gallery (
                    photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER,
                    uploaded_by TEXT,
                    photo_path TEXT,
                    caption TEXT,
                    upload_date TEXT,
                    is_featured BOOLEAN DEFAULT 0,
                    FOREIGN KEY (event_id) REFERENCES alumni_events (event_id),
                    FOREIGN KEY (uploaded_by) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create privacy_consent table
        cursor.execute('''
        CREATE TABLE privacy_consent (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        consent_type TEXT NOT NULL,
                        granted INTEGER NOT NULL,
                        granted_at TEXT NOT NULL,
                        expires_at TEXT,
                        version TEXT NOT NULL,
                        UNIQUE(student_id, consent_type)
                    )
        ''')

        # Create processing_queue table
        cursor.execute('''
        CREATE TABLE processing_queue (
                        id TEXT PRIMARY KEY,
                        submission_data TEXT NOT NULL,
                        priority INTEGER DEFAULT 1,
                        status TEXT DEFAULT 'queued',
                        created_at TEXT NOT NULL,
                        processed_at TEXT
                    )
        ''')

        # Create project_milestones table
        cursor.execute('''
        CREATE TABLE project_milestones (
                            id TEXT PRIMARY KEY,
                            project_name TEXT NOT NULL,
                            milestone_name TEXT NOT NULL,
                            due_date TEXT NOT NULL,
                            completion_percentage REAL DEFAULT 0.0,
                            status TEXT DEFAULT 'pending',
                            course_id TEXT,
                            student_id TEXT,
                            description TEXT,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY (course_id) REFERENCES courses (id),
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create provider_schedules table
        cursor.execute('''
        CREATE TABLE provider_schedules (
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

        # Create ranked_votes table
        cursor.execute('''
        CREATE TABLE ranked_votes (
                    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    election_id INTEGER,
                    voter_id TEXT,
                    candidate_preferences TEXT,  -- JSON string of ranked preferences
                    vote_time TEXT,
                    FOREIGN KEY (election_id) REFERENCES union_elections (election_id),
                    FOREIGN KEY (voter_id) REFERENCES students (student_id)
                )
        ''')

        # Create recommended_interventions table
        cursor.execute('''
        CREATE TABLE recommended_interventions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    risk_factor_id INTEGER,
                    intervention_type_id INTEGER,
                    recommended_date TEXT,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (risk_factor_id) REFERENCES risk_factors (id),
                    FOREIGN KEY (intervention_type_id) REFERENCES intervention_types (id)
                )
        ''')

        # Create referrals table
        cursor.execute('''
        CREATE TABLE referrals (
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

        # Create resources table
        cursor.execute('''
        CREATE TABLE resources (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            type TEXT NOT NULL,
                            capacity INTEGER,
                            location TEXT,
                            equipment TEXT,
                            status TEXT DEFAULT 'available',
                            date_added TEXT NOT NULL
                        )
        ''')

        # Create risk_assessments table
        cursor.execute('''
        CREATE TABLE risk_assessments (
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

        # Create risk_factors table
        cursor.execute('''
        CREATE TABLE risk_factors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    factor_name TEXT,
                    factor_value REAL,
                    assessment_id INTEGER,
                    date_calculated TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
                )
        ''')

        # Create rubric_criteria table
        cursor.execute('''
        CREATE TABLE rubric_criteria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rubric_id INTEGER NOT NULL,
                    criteria_name TEXT NOT NULL,
                    description TEXT,
                    max_points REAL NOT NULL,
                    weight REAL DEFAULT 1.0,
                    display_order INTEGER DEFAULT 0,
                    FOREIGN KEY (rubric_id) REFERENCES rubrics (id) ON DELETE CASCADE
                )
        ''')

        # Create rubrics table
        cursor.execute('''
        CREATE TABLE rubrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    total_points REAL NOT NULL DEFAULT 100,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by INTEGER,
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
        ''')

        # Create schedule_conflicts table
        cursor.execute('''
        CREATE TABLE schedule_conflicts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conflict_type TEXT,
                        description TEXT,
                        affected_schedules TEXT,
                        resolved BOOLEAN DEFAULT 0,
                        resolution_notes TEXT,
                        detected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resolved_date TIMESTAMP
                    )
        ''')

        # Create schedule_history table
        cursor.execute('''
        CREATE TABLE schedule_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schedule_id INTEGER,
                        action TEXT,
                        old_values TEXT,
                        new_values TEXT,
                        changed_by TEXT,
                        change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
        ''')

        # Create school_calendar table
        cursor.execute('''
        CREATE TABLE school_calendar (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_name TEXT,
                        event_description TEXT,
                        event_date TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        location TEXT,
                        event_type TEXT,
                        audience TEXT
                    )
        ''')

        # Create screening_schedules table
        cursor.execute('''
        CREATE TABLE screening_schedules (
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

        # Create search_presets table
        cursor.execute('''
        CREATE TABLE search_presets (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            user_id TEXT NOT NULL,
                            filters TEXT NOT NULL,
                            date_added TEXT NOT NULL,
                            is_active BOOLEAN DEFAULT TRUE
                        )
        ''')

        # Create shared_resources table
        cursor.execute('''
        CREATE TABLE shared_resources (
                    resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uploader_id TEXT,
                    resource_title TEXT,
                    resource_type TEXT,
                    subject TEXT,
                    file_path TEXT,
                    description TEXT,
                    upload_date TEXT,
                    downloads INTEGER DEFAULT 0,
                    rating REAL DEFAULT 0.0,
                    FOREIGN KEY (uploader_id) REFERENCES students (student_id)
                )
        ''')

        # Create sla_policies table
        cursor.execute('''
        CREATE TABLE sla_policies (
                    sla_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    priority TEXT,
                    impact TEXT,
                    urgency TEXT,
                    first_response_hours INTEGER,
                    resolution_hours INTEGER,
                    escalation_hours INTEGER,
                    business_hours_only BOOLEAN DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create staff_schedules table
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

        # Create survey_responses table
        cursor.execute('''
        CREATE TABLE survey_responses (
                    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    survey_id INTEGER,
                    alumni_id TEXT,
                    responses TEXT,
                    submission_date TEXT,
                    FOREIGN KEY (survey_id) REFERENCES event_surveys (survey_id),
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
                )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="other"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="other", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# PARENT TABLES (6 tables)
# ============================================================================


