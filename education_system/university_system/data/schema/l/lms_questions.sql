CREATE TABLE IF NOT EXISTS lms_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT NOT NULL DEFAULT 'multiple_choice',
            options_json TEXT,
            correct_answer TEXT NOT NULL,
            marks REAL NOT NULL DEFAULT 1.0,
            order_index INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (quiz_id) REFERENCES lms_quizzes(id)
        );
