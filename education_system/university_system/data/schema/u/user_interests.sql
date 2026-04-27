CREATE TABLE IF NOT EXISTS user_interests (
                interest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                interest_category TEXT NOT NULL,
                interest_name TEXT NOT NULL,
                interest_level INTEGER DEFAULT 5,
                is_public INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username),
                UNIQUE(user_id, interest_category, interest_name)
            );
