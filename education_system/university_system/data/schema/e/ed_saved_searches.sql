CREATE TABLE IF NOT EXISTS ed_saved_searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner TEXT NOT NULL,
        name TEXT NOT NULL,
        query TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(owner, name)
    );
