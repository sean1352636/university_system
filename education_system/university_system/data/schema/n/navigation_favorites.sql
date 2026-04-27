CREATE TABLE IF NOT EXISTS navigation_favorites (
                    favorite_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    location_type TEXT NOT NULL,
                    location_id INTEGER NOT NULL,
                    nickname TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
