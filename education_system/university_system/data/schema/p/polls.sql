CREATE TABLE IF NOT EXISTS polls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            poll_type TEXT DEFAULT 'movie_choice',
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            max_votes_per_user INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
