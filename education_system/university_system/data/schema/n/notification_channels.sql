CREATE TABLE IF NOT EXISTS notification_channels (
                    channel_setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    min_priority TEXT DEFAULT 'low',
                    push_enabled INTEGER DEFAULT 1,
                    email_enabled INTEGER DEFAULT 1,
                    sms_enabled INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, channel),
                    FOREIGN KEY (user_id) REFERENCES users(username)
                );
