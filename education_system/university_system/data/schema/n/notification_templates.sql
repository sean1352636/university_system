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
        );
