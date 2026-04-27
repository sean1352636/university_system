CREATE TABLE IF NOT EXISTS reading_lists (
            list_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            creator_id TEXT NOT NULL,
            created_date TEXT NOT NULL,
            is_public BOOLEAN DEFAULT FALSE,
            is_collaborative BOOLEAN DEFAULT FALSE,
            category TEXT,
            target_reading_level TEXT
        );
