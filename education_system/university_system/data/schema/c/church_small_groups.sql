CREATE TABLE IF NOT EXISTS church_small_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    leader TEXT,
    meeting_day TEXT,
    meeting_time TEXT,
    location TEXT,
    description TEXT,
    members TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
