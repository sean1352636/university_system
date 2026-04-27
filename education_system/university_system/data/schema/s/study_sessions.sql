CREATE TABLE IF NOT EXISTS study_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    module_code TEXT,
                    topic TEXT,
                    duration_minutes INTEGER DEFAULT 0,
                    effectiveness_rating INTEGER,
                    notes TEXT,
                    studied_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
