CREATE TABLE IF NOT EXISTS event_announcements (
            announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            announcement_text TEXT NOT NULL,
            sent_to TEXT NOT NULL,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sent_by TEXT,
            FOREIGN KEY (event_id) REFERENCES campus_events (event_id)
        );
