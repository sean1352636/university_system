CREATE TABLE IF NOT EXISTS course_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            semester TEXT NOT NULL,
            year INTEGER NOT NULL,
            total_enrolled INTEGER DEFAULT 0,
            total_completed INTEGER DEFAULT 0,
            average_grade REAL DEFAULT 0.0,
            completion_rate REAL DEFAULT 0.0,
            calculated_at TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        );
