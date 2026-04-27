CREATE TABLE IF NOT EXISTS early_warning_tutoring_recommendations (
            recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            recommended_by TEXT NOT NULL,
            recommendation_type TEXT NOT NULL,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            tutor_assigned TEXT,
            sessions_scheduled INTEGER DEFAULT 0,
            sessions_completed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        );
