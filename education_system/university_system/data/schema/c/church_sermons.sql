CREATE TABLE IF NOT EXISTS church_sermons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    speaker TEXT,
    date TEXT,
    scripture TEXT,
    summary TEXT,
    video_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
