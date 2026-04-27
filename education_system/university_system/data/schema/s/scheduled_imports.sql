CREATE TABLE IF NOT EXISTS scheduled_imports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schedule_type TEXT NOT NULL,
                        schedule_data TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );
