CREATE TABLE IF NOT EXISTS interest_matches (
                match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id TEXT NOT NULL,
                user2_id TEXT NOT NULL,
                compatibility_score REAL NOT NULL,
                shared_interests TEXT,
                match_reason TEXT,
                match_status TEXT DEFAULT 'suggested',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user1_id) REFERENCES users(username),
                FOREIGN KEY (user2_id) REFERENCES users(username),
                UNIQUE(user1_id, user2_id)
            );
