CREATE TABLE IF NOT EXISTS parent_preferences (
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
        );
