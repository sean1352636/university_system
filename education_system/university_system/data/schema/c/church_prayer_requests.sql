CREATE TABLE IF NOT EXISTS church_prayer_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_name TEXT,
    request TEXT,
    category TEXT,
    status TEXT DEFAULT 'Pending',
    date TEXT,
    is_anonymous INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
