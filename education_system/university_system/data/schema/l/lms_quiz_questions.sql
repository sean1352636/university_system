CREATE TABLE IF NOT EXISTS lms_quiz_questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                question_type TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                points INTEGER DEFAULT 1,
                options TEXT,
                explanation TEXT,
                display_order INTEGER DEFAULT 0, "created_at" TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (quiz_id) REFERENCES lms_quizzes(quiz_id) ON DELETE CASCADE
            );
