CREATE TABLE IF NOT EXISTS timetable_student_preferences (
            preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            preference_type TEXT NOT NULL,
            preferred_days TEXT,
            preferred_times TEXT,
            avoid_days TEXT,
            avoid_times TEXT,
            max_daily_hours INTEGER,
            gap_preference TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
