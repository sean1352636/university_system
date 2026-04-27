CREATE TABLE IF NOT EXISTS mental_health_counselors (
            counselor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            specialization TEXT,
            qualifications TEXT,
            availability_schedule TEXT,
            max_daily_appointments INTEGER DEFAULT 8,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        , "updated_at" TEXT DEFAULT CURRENT_TIMESTAMP);
