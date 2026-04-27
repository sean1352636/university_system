CREATE TABLE IF NOT EXISTS early_warning_notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            recipient_type TEXT NOT NULL,
            recipient_email TEXT NOT NULL,
            notification_type TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_read BOOLEAN DEFAULT 0,
            read_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
