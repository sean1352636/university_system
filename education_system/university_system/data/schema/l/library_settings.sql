CREATE TABLE IF NOT EXISTS library_settings (
                setting_name TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL,
                description TEXT,
                setting_type TEXT DEFAULT 'string',
                min_value REAL,
                max_value REAL,
                allowed_values TEXT
            );
