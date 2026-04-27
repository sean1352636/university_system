CREATE TABLE IF NOT EXISTS mobile_preferences (
                pref_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                notifications_enabled BOOLEAN DEFAULT 1,
                dark_mode BOOLEAN DEFAULT 0,
                language TEXT DEFAULT 'en',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, theme TEXT DEFAULT 'light', offline_mode_enabled BOOLEAN DEFAULT 1, data_saver_mode BOOLEAN DEFAULT 0, auto_sync BOOLEAN DEFAULT 1, "biometric_enabled" BOOLEAN DEFAULT 0, "data_saver_enabled" BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
