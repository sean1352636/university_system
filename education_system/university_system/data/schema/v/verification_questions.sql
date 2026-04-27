CREATE TABLE IF NOT EXISTS verification_questions (
                    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    found_item_id INTEGER NOT NULL,
                    question_text TEXT NOT NULL,
                    expected_answer_type TEXT DEFAULT 'text',
                    created_by TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (found_item_id) REFERENCES found_items(item_id) ON DELETE CASCADE
                );
