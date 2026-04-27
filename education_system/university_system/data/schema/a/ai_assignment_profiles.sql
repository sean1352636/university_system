CREATE TABLE IF NOT EXISTS ai_assignment_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    course TEXT,
                    expected_word_count INTEGER,
                    assignment_type TEXT,
                    baseline_ai_score REAL,
                    baseline_vocab_diversity REAL,
                    baseline_sentence_complexity REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
