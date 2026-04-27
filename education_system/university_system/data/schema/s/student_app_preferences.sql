CREATE TABLE IF NOT EXISTS student_app_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT UNIQUE NOT NULL,
                    theme TEXT DEFAULT 'light',
                    notifications_enabled INTEGER DEFAULT 1,
                    language TEXT DEFAULT 'en',
                    dashboard_layout TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
