CREATE TABLE IF NOT EXISTS training_enrollments (
                    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    course_id INTEGER NOT NULL,
                    enrolled_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    due_date TEXT,
                    started_date TEXT,
                    completed_date TEXT,
                    status TEXT DEFAULT 'enrolled',
                    score REAL,
                    attempts INTEGER DEFAULT 0,
                    certificate_path TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (course_id) REFERENCES training_courses(course_id)
                );
