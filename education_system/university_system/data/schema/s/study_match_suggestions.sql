CREATE TABLE IF NOT EXISTS study_match_suggestions (
                    suggestion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    suggested_student_id TEXT NOT NULL,
                    course_id TEXT,
                    compatibility_score REAL DEFAULT 0.0,
                    match_reason TEXT,
                    status TEXT DEFAULT 'Pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    responded_at TEXT
                );
