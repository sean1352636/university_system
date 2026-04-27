CREATE TABLE IF NOT EXISTS lms_quizzes (
                quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lms_course_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                duration_minutes INTEGER DEFAULT 60,
                passing_score REAL DEFAULT 70.0,
                max_attempts INTEGER DEFAULT 1,
                available_from TEXT,
                available_until TEXT,
                is_published INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')), "randomize_questions" BOOLEAN DEFAULT 0, "show_correct_answers" BOOLEAN DEFAULT 1, "updated_at" TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id) ON DELETE CASCADE
            );
