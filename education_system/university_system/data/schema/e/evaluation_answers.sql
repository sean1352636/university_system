CREATE TABLE IF NOT EXISTS evaluation_answers (
                answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                response_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                answer_value TEXT,
                numeric_value REAL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (response_id) REFERENCES evaluation_responses(response_id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES evaluation_questions(question_id) ON DELETE CASCADE
            );
