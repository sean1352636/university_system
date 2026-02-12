"""
Database schema for Unified Communication Hub
Handles email, SMS, push notifications, and announcements
"""

from university_system.modules.shared.utils.i18n import get_text, _

COMMUNICATION_SCHEMA = """
-- Messages
CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,
    subject TEXT,
    body TEXT NOT NULL,
    message_type TEXT DEFAULT 'email',  -- email, sms, push, announcement
    priority TEXT DEFAULT 'normal',  -- low, normal, high, urgent
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scheduled_time TIMESTAMP,
    status TEXT DEFAULT 'draft'  -- draft, queued, sent, failed
);

-- Message Recipients
CREATE TABLE IF NOT EXISTS message_recipients (
    recipient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    delivery_status TEXT DEFAULT 'pending',  -- pending, sent, delivered, failed, read
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (message_id) REFERENCES messages(message_id) ON DELETE CASCADE
);

-- Email Queue
CREATE TABLE IF NOT EXISTS email_queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    to_address TEXT NOT NULL,
    cc_addresses TEXT,  -- JSON array
    bcc_addresses TEXT,  -- JSON array
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    html_body TEXT,
    attachments TEXT,  -- JSON array of file paths
    scheduled_time TIMESTAMP,
    priority INTEGER DEFAULT 5,
    status TEXT DEFAULT 'queued',  -- queued, sending, sent, failed
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    sent_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SMS Queue
CREATE TABLE IF NOT EXISTS sms_queue (
    sms_id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number TEXT NOT NULL,
    message_text TEXT NOT NULL,
    scheduled_time TIMESTAMP,
    status TEXT DEFAULT 'queued',  -- queued, sending, sent, failed
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    sent_at TIMESTAMP,
    message_id TEXT,  -- Provider message ID
    error_message TEXT,
    cost REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Push Notifications
CREATE TABLE IF NOT EXISTS push_notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    data TEXT,  -- JSON for additional data
    icon TEXT,
    click_action TEXT,
    status TEXT DEFAULT 'pending',  -- pending, sent, failed
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Announcements
CREATE TABLE IF NOT EXISTS announcements (
    announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    target_audience TEXT,  -- JSON: {role: [...], department: [...]}
    priority TEXT DEFAULT 'normal',  -- low, normal, high, urgent
    start_date DATE,
    end_date DATE,
    is_active BOOLEAN DEFAULT 1,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Message Templates
CREATE TABLE IF NOT EXISTS message_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    subject TEXT,
    body TEXT NOT NULL,
    variables TEXT,  -- JSON array of variable names
    template_type TEXT DEFAULT 'email',  -- email, sms, push, announcement
    category TEXT,  -- academic, administrative, emergency, marketing
    is_active BOOLEAN DEFAULT 1,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Communication Preferences
CREATE TABLE IF NOT EXISTS communication_preferences (
    pref_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    email_enabled BOOLEAN DEFAULT 1,
    sms_enabled BOOLEAN DEFAULT 0,
    push_enabled BOOLEAN DEFAULT 1,
    announcement_enabled BOOLEAN DEFAULT 1,
    marketing_enabled BOOLEAN DEFAULT 0,
    emergency_only BOOLEAN DEFAULT 0,
    preferred_method TEXT DEFAULT 'email',
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Delivery Logs
CREATE TABLE IF NOT EXISTS delivery_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER,
    recipient_id INTEGER,
    delivery_method TEXT NOT NULL,  -- email, sms, push
    delivery_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,  -- success, failed, bounced
    error_message TEXT,
    response_code TEXT,
    provider_message_id TEXT,
    FOREIGN KEY (message_id) REFERENCES messages(message_id)
);

-- Emergency Alerts
CREATE TABLE IF NOT EXISTS emergency_alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,  -- weather, security, health, facility
    message TEXT NOT NULL,
    severity TEXT DEFAULT 'moderate',  -- low, moderate, high, critical
    affected_locations TEXT,  -- JSON array
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    sent_by INTEGER NOT NULL,
    total_recipients INTEGER DEFAULT 0
);

-- Notification Subscriptions
CREATE TABLE IF NOT EXISTS notification_subscriptions (
    subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    topic TEXT NOT NULL,  -- course_updates, events, grades, announcements
    channel TEXT DEFAULT 'email',  -- email, sms, push
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    UNIQUE(user_id, topic, channel)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_message_recipients_user ON message_recipients(user_id);
CREATE INDEX IF NOT EXISTS idx_email_queue_status ON email_queue(status);
CREATE INDEX IF NOT EXISTS idx_sms_queue_status ON sms_queue(status);
CREATE INDEX IF NOT EXISTS idx_push_notifications_user ON push_notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_announcements_active ON announcements(is_active);
CREATE INDEX IF NOT EXISTS idx_delivery_logs_message ON delivery_logs(message_id);
CREATE INDEX IF NOT EXISTS idx_emergency_alerts_active ON emergency_alerts(is_active);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON notification_subscriptions(user_id);
"""

def create_communication_tables(conn):
    """Create all communication hub tables"""
    cursor = conn.cursor()
    cursor.executescript(COMMUNICATION_SCHEMA)
    conn.commit()
    print("Unified Communication Hub tables created successfully")

if __name__ == "__main__":
    from university_system.infrastructure.database.db import sqlite3
    from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH

    with sqlite3.connect(DEFAULT_DB_PATH) as conn:
        create_communication_tables(conn)
