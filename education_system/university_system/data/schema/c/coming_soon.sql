CREATE TABLE IF NOT EXISTS coming_soon (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            genre TEXT,
            rating TEXT,
            director TEXT,
            release_date TEXT NOT NULL,
            trailer_url TEXT,
            poster_url TEXT,
            notify_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'upcoming',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
