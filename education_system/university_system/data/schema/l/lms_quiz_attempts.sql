CREATE TABLE IF NOT EXISTS lms_quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            answers_json TEXT,
            score REAL,
            passed INTEGER NOT NULL DEFAULT 0,
            attempted_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (quiz_id) REFERENCES lms_quizzes(id)
        );
