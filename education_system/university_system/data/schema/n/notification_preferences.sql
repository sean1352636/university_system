CREATE TABLE IF NOT EXISTS notification_preferences (
                    preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    quiet_hours_start TEXT,
                    quiet_hours_end TEXT,
                    daily_digest_enabled INTEGER DEFAULT 0,
                    daily_digest_time TEXT DEFAULT '08:00',
                    bundle_notifications INTEGER DEFAULT 1,
                    bundle_time_window INTEGER DEFAULT 300,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "advance_time" INTEGER DEFAULT 60, "date_added" TEXT, "enabled" BOOLEAN DEFAULT TRUE, "id" INTEGER, "method" TEXT DEFAULT 'email', "notification_type" TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(username)
                );
