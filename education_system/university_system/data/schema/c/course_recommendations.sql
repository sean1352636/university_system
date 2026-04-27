CREATE TABLE IF NOT EXISTS course_recommendations (
                    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    recommendation_reason TEXT NOT NULL,
                    relevance_score REAL DEFAULT 0.0,
                    semester_recommended TEXT,
                    prerequisites_met BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id),
                    FOREIGN KEY (course_id) REFERENCES courses(code)
                );
