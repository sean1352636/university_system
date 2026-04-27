CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_id INTEGER NOT NULL,
            question_type TEXT NOT NULL CHECK (question_type IN ('mcq', 'fill_blank', 'coding')),
            question_text TEXT NOT NULL,
            options_json TEXT,
            correct_answer TEXT,
            points REAL DEFAULT 1.0,
            difficulty TEXT DEFAULT 'medium' CHECK (difficulty IN ('easy', 'medium', 'hard')),
            topic TEXT,
            time_limit_seconds INTEGER,
            test_cases_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bank_id) REFERENCES question_banks (id) ON DELETE CASCADE
        );
