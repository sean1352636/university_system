CREATE TABLE IF NOT EXISTS provider_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_name TEXT,
                    day_of_week INTEGER,
                    start_time TEXT,
                    end_time TEXT,
                    max_appointments INTEGER DEFAULT 10,
                    specialty TEXT,
                    location TEXT,
                    active INTEGER DEFAULT 1,
                    created_at TEXT
                );
