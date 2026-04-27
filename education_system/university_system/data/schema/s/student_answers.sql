CREATE TABLE IF NOT EXISTS student_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            submission_id INTEGER,
            answer_text TEXT,
            is_correct INTEGER DEFAULT 0,
            points_earned REAL DEFAULT 0,
            time_spent_seconds INTEGER,
            answered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (question_id) REFERENCES questions (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id)
        );
