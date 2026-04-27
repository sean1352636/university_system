CREATE TABLE IF NOT EXISTS event_sponsors (
            sponsor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            sponsor_name TEXT NOT NULL,
            sponsor_type TEXT,
            contribution_amount REAL,
            logo_url TEXT,
            website_url TEXT,
            FOREIGN KEY (event_id) REFERENCES campus_events (event_id)
        );
