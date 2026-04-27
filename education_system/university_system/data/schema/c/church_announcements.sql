CREATE TABLE IF NOT EXISTS church_announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    content TEXT,
    date TEXT,
    priority TEXT,
    expires TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
