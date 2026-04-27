CREATE TABLE IF NOT EXISTS user_personality (
                personality_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE,
                personality_type TEXT,
                extroversion_score INTEGER,
                openness_score INTEGER,
                social_preference TEXT,
                group_size_preference TEXT,
                activity_level TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username)
            );
