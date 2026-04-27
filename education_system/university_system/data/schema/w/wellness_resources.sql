CREATE TABLE IF NOT EXISTS wellness_resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                contact TEXT,
                url TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
