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
        );
