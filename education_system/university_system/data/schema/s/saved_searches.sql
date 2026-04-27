CREATE TABLE IF NOT EXISTS saved_searches (
            search_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            search_criteria TEXT,
            created_at TEXT, search_name TEXT, created_date TEXT, is_shared INTEGER DEFAULT 0, last_used TEXT, "search_type" TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
