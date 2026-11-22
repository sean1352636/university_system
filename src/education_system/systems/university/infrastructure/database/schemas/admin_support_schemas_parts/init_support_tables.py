"""Extracted function implementation."""

from .. import admin_support_schemas_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def init_support_tables():
    """Initialize support system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="support"))

        # Create escalation_rules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS escalation_rules (
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
        CREATE TABLE IF NOT EXISTS faqs (
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
        CREATE TABLE IF NOT EXISTS peer_support_groups (
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
        CREATE TABLE IF NOT EXISTS support_group_members (
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
        CREATE TABLE IF NOT EXISTS support_resources (
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

        # support_tickets, ticket_responses and ticket_attachments: one
        # definition, owned by the Student Support schema (shared with the
        # Helpdesk).
        from education_system.systems.university.domains.student_support.domain.student_support import (
            schema as support_schema,
        )
        support_schema.apply(cursor.execute)

        # Create ticket_audit_log table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_audit_log (
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
        CREATE TABLE IF NOT EXISTS ticket_escalations (
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
        CREATE TABLE IF NOT EXISTS ticket_links (
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
        CREATE TABLE IF NOT EXISTS ticket_replies (
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

        # Create ticket_templates table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    priority TEXT,
                    subject_template TEXT,
                    message_template TEXT,
                    default_impact TEXT,
                    default_urgency TEXT,
                    form_fields TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    usage_count INTEGER DEFAULT 0,
                    created_by TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create ticket_time_tracking table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_time_tracking (
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
        CREATE TABLE IF NOT EXISTS ticket_workflows (
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
