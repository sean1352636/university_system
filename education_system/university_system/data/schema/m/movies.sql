CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            duration INTEGER NOT NULL,
            genre TEXT,
            rating TEXT,
            description TEXT,
            release_date TEXT,
            director TEXT,
            poster_url TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        , trailer_url TEXT, age_rating TEXT, language TEXT DEFAULT 'en');
