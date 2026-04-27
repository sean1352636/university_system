CREATE TABLE IF NOT EXISTS institutions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT,
                country TEXT,
                created_at TEXT NOT NULL
            );
