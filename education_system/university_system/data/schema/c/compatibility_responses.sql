CREATE TABLE IF NOT EXISTS compatibility_responses (
                    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    response_value TEXT NOT NULL,
                    importance_level TEXT DEFAULT 'Medium',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id) REFERENCES roommate_profiles(profile_id) ON DELETE CASCADE
                );
