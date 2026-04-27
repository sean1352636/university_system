CREATE TABLE IF NOT EXISTS library_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT NOT NULL,
                event_date TEXT NOT NULL,
                event_time TEXT NOT NULL,
                location TEXT,
                description TEXT,
                max_capacity INTEGER DEFAULT 50,
                registered_count INTEGER DEFAULT 0,
                created_by TEXT,
                created_at TEXT
            );
