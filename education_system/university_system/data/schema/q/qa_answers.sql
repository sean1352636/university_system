CREATE TABLE IF NOT EXISTS qa_answers (
                    answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    anonymous_id TEXT NOT NULL,
                    answer_text TEXT NOT NULL,
                    upvotes INTEGER DEFAULT 0,
                    downvotes INTEGER DEFAULT 0,
                    is_accepted BOOLEAN DEFAULT 0,
                    is_instructor_answer BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (question_id) REFERENCES qa_board(question_id) ON DELETE CASCADE
                );
