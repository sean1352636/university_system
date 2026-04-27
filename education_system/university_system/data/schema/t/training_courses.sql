CREATE TABLE IF NOT EXISTS training_courses (
                    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    provider TEXT,
                    duration_hours REAL,
                    passing_score REAL DEFAULT 70,
                    is_mandatory BOOLEAN DEFAULT 0,
                    recertification_months INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
