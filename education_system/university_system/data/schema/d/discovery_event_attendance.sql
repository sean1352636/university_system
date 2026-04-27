CREATE TABLE IF NOT EXISTS discovery_event_attendance (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    check_in_time TEXT NOT NULL,
    check_out_time TEXT,
    FOREIGN KEY (event_id) REFERENCES campus_events(event_id),
    UNIQUE(event_id, user_id)
);
