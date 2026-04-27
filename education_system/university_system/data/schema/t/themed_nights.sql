CREATE TABLE IF NOT EXISTS themed_nights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            theme_type TEXT NOT NULL,
            description TEXT,
            day_of_week INTEGER,
            discount_percent REAL DEFAULT 0,
            genre_filter TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
