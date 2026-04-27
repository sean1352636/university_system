CREATE TABLE IF NOT EXISTS mental_health_meditation_tracking (
            tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            session_id INTEGER NOT NULL,
            completion_percentage INTEGER DEFAULT 0,
            completed_at TEXT,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES mental_health_meditation_sessions (session_id)
        );
