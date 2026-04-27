CREATE TABLE IF NOT EXISTS notification_type_preferences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        notification_type TEXT NOT NULL,
                        email_enabled INTEGER DEFAULT 1,
                        sms_enabled INTEGER DEFAULT 0,
                        push_enabled INTEGER DEFAULT 1,
                        in_app_enabled INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP,
                        UNIQUE(user_id, notification_type)
                    );
