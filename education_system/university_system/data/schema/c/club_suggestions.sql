CREATE TABLE IF NOT EXISTS club_suggestions (
                suggestion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                club_name TEXT NOT NULL,
                club_category TEXT NOT NULL,
                match_score REAL NOT NULL,
                reason TEXT,
                status TEXT DEFAULT 'suggested',
                suggested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username)
            );
