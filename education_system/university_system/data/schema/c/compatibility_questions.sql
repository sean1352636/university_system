CREATE TABLE IF NOT EXISTS compatibility_questions (
                    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    response_type TEXT DEFAULT 'scale',
                    options TEXT,
                    weight REAL DEFAULT 1.0,
                    is_active BOOLEAN DEFAULT 1
                );
