CREATE TABLE IF NOT EXISTS attendance_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_name TEXT UNIQUE,
            setting_value TEXT,
            description TEXT,
            category TEXT DEFAULT 'general',
            data_type TEXT DEFAULT 'string',
            last_modified TEXT DEFAULT CURRENT_TIMESTAMP
        );
