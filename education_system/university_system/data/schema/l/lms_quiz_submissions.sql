CREATE TABLE IF NOT EXISTS lms_quiz_submissions (
                submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                score REAL NOT NULL,
                total_points INTEGER NOT NULL,
                time_taken_minutes INTEGER,
                submitted_at TEXT NOT NULL DEFAULT (datetime('now')), "graded_at" TEXT, "graded_by" TEXT,
                FOREIGN KEY (quiz_id) REFERENCES lms_quizzes(quiz_id) ON DELETE CASCADE
            );
