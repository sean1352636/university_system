CREATE TABLE IF NOT EXISTS ai_detector_baselines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id TEXT UNIQUE NOT NULL,
                    avg_sentence_length REAL,
                    vocabulary_complexity REAL,
                    avg_word_count REAL,
                    samples_analyzed INTEGER,
                    created_at TEXT NOT NULL
                );
