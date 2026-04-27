CREATE TABLE IF NOT EXISTS discovery_event_rsvps (
    rsvp_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    rsvp_status TEXT NOT NULL,
    rsvp_date TEXT DEFAULT CURRENT_TIMESTAMP,
    added_to_calendar INTEGER DEFAULT 0,
    reminder_sent INTEGER DEFAULT 0,
    FOREIGN KEY (event_id) REFERENCES campus_events(event_id),
    UNIQUE(event_id, user_id)
);
