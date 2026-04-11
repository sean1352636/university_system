from __future__ import annotations
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.university_system.core.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_email_system_db():
    """Initialize email system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="email system"))

        # Email log table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            status TEXT DEFAULT 'sent',
            error_message TEXT
        )
        ''')

        # Email templates table - check if it exists first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_templates'")
        if not cursor.fetchone():
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                created_by TEXT,
                is_shared INTEGER DEFAULT 0,
                version INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            )
            ''')
        else:
            # Add category column if it doesn't exist (for existing tables)
            cursor.execute("PRAGMA table_info(email_templates)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'category' not in columns:
                cursor.execute("ALTER TABLE email_templates ADD COLUMN category TEXT")

        # Create index only if category column exists
        cursor.execute("PRAGMA table_info(email_templates)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'category' in columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_templates_category ON email_templates(category)")

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Email system"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="email", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# HEALTH SYSTEM SCHEMAS
# ============================================================================


def init_communication_tables():
    """Initialize communication system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="communication"))

        # Create announcement_reads table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcement_reads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        announcement_id INTEGER,
                        parent_id TEXT,
                        read_date TEXT,
                        acknowledged BOOLEAN DEFAULT 0,
                        FOREIGN KEY (announcement_id) REFERENCES school_announcements (id),
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
                    )
        ''')

        # Create announcement_viewers table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcement_viewers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        announcement_id INTEGER NOT NULL,
                        viewer_id INTEGER NOT NULL,
                        viewed_at TEXT NOT NULL,
                        FOREIGN KEY (announcement_id) REFERENCES announcements (id),
                        FOREIGN KEY (viewer_id) REFERENCES users (id)
                    )
        ''')

        # Create chat_messages table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        room_id INTEGER NOT NULL,
                        sender_id INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        sent_at TEXT NOT NULL,
                        FOREIGN KEY (room_id) REFERENCES chat_rooms (id),
                        FOREIGN KEY (sender_id) REFERENCES users (id)
                    )
        ''')

        # Create communication_log table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS communication_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        action_type TEXT NOT NULL,
                        action_details TEXT,
                        performed_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
        ''')

        # Create emails table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            recipient TEXT NOT NULL,
                            subject TEXT,
                            body TEXT,
                            cc TEXT,
                            bcc TEXT,
                            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            status TEXT DEFAULT 'sent',
                            attachments TEXT
                        )
        ''')

        # Create group_message_recipients table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_message_recipients (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_id INTEGER NOT NULL,
                        recipient_id INTEGER NOT NULL,
                        is_read INTEGER DEFAULT 0,
                        is_archived INTEGER DEFAULT 0,
                        is_deleted INTEGER DEFAULT 0,
                        read_at TEXT,
                        FOREIGN KEY (message_id) REFERENCES group_messages (id),
                        FOREIGN KEY (recipient_id) REFERENCES users (id)
                    )
        ''')

        # Create group_messages table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sender_id INTEGER NOT NULL,
                        group_type TEXT NOT NULL,
                        group_id TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        content TEXT NOT NULL,
                        attachment_path TEXT,
                        sent_at TEXT NOT NULL,
                        FOREIGN KEY (sender_id) REFERENCES users (id)
                    )
        ''')

        # Create notification_preferences table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notification_preferences (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id TEXT NOT NULL,
                            notification_type TEXT NOT NULL,
                            enabled BOOLEAN DEFAULT TRUE,
                            advance_time INTEGER DEFAULT 60,
                            method TEXT DEFAULT 'email',
                            date_added TEXT NOT NULL,
                            UNIQUE(user_id, notification_type)
                        )
        ''')

        # Create notification_queue table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notification_queue (
                            id TEXT PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            event_id TEXT,
                            notification_type TEXT NOT NULL,
                            scheduled_time TEXT NOT NULL,
                            status TEXT DEFAULT 'pending',
                            message TEXT,
                            date_added TEXT NOT NULL,
                            sent_at TEXT,
                            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
                        )
        ''')

        # Create notification_schedules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notification_schedules (
                    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    trigger_condition TEXT NOT NULL, -- JSON with conditions
                    days_before_due INTEGER,
                    max_reminders INTEGER DEFAULT 3,
                    reminder_interval_days INTEGER DEFAULT 7,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (template_id) REFERENCES notification_templates (template_id)
                )
        ''')

        # Create notification_templates table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notification_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_name TEXT NOT NULL,
                    template_type TEXT NOT NULL, -- 'payment_reminder', 'overdue_notice', 'payment_confirmation', etc.
                    subject_template TEXT NOT NULL,
                    body_template TEXT NOT NULL,
                    send_method TEXT DEFAULT 'email', -- 'email', 'sms', 'push'
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create notifications table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    notification_type TEXT NOT NULL,
                    related_ticket_id INTEGER,
                    is_read BOOLEAN DEFAULT 0,
                    created_datetime TEXT NOT NULL,
                    read_datetime TEXT,
                    expires_at TEXT,
                    data TEXT, assignment_id INTEGER, recipient_type TEXT, recipient_id TEXT, sent BOOLEAN DEFAULT 0, created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- JSON data
                    FOREIGN KEY (related_ticket_id) REFERENCES support_tickets (ticket_id)
                )
        ''')

        # Create school_announcements table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS school_announcements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        content TEXT,
                        priority TEXT DEFAULT 'normal',
                        category TEXT,
                        audience TEXT,
                        created_by INTEGER,
                        created_date TEXT,
                        expiry_date TEXT,
                        requires_acknowledgment BOOLEAN DEFAULT 0,
                        FOREIGN KEY (created_by) REFERENCES users (id)
                    )
        ''')

        # Create sent_notifications table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    template_id INTEGER NOT NULL,
                    recipient_email TEXT,
                    recipient_phone TEXT,
                    subject TEXT,
                    message_body TEXT,
                    send_method TEXT,
                    status TEXT DEFAULT 'pending', -- pending, sent, failed, bounced
                    sent_at TEXT,
                    error_message TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (template_id) REFERENCES notification_templates (template_id)
                )
        ''')

        # Create stored_emails table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stored_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient_email TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    sender_email TEXT NOT NULL,
                    sender_name TEXT NOT NULL,
                    cc_recipients TEXT,
                    bcc_recipients TEXT,
                    attachment_paths TEXT,
                    created_date TEXT NOT NULL,
                    template_name TEXT,
                    template_vars TEXT,
                    related_to TEXT,
                    student_id TEXT
                )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="communication"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="communication", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# COURSES TABLES (11 tables)
# ============================================================================


