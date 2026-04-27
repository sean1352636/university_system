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
        );
