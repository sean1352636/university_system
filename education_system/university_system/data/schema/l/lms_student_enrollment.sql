CREATE TABLE IF NOT EXISTS lms_student_enrollment (
                enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lms_course_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                enrollment_date TEXT NOT NULL DEFAULT (datetime('now')),
                last_accessed TEXT,
                progress_percentage REAL DEFAULT 0.0,
                is_active INTEGER DEFAULT 1, "progress_percent" REAL DEFAULT 0, "enrolled_at" TIMESTAMP DEFAULT NULL,
                FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id) ON DELETE CASCADE,
                UNIQUE(lms_course_id, student_id)
            );
