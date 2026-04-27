CREATE TABLE IF NOT EXISTS discovery_event_photos (
    photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    photo_url TEXT NOT NULL,
    caption TEXT,
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES campus_events(event_id)
);
