CREATE TABLE IF NOT EXISTS event_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    color_code TEXT,
                    date_added TEXT NOT NULL
                );
