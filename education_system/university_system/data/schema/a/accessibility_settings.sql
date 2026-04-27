CREATE TABLE IF NOT EXISTS accessibility_settings (
            setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            theme TEXT DEFAULT 'standard',
            font_size INTEGER DEFAULT 16,
            contrast_level TEXT DEFAULT 'normal',
            screen_reader_enabled BOOLEAN DEFAULT 0,
            keyboard_navigation BOOLEAN DEFAULT 0, "student_id" TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
