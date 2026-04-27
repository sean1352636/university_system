CREATE TABLE IF NOT EXISTS user_privacy_settings (
                privacy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE,
                allow_matching INTEGER DEFAULT 1,
                show_profile INTEGER DEFAULT 1,
                allow_messages INTEGER DEFAULT 1,
                show_interests INTEGER DEFAULT 1,
                show_in_search INTEGER DEFAULT 1,
                match_same_major INTEGER DEFAULT 0,
                match_same_year INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username)
            );
