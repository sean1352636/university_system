CREATE TABLE IF NOT EXISTS sc_announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        message TEXT,
        priority TEXT,
        posted_by TEXT,
        posted_at TEXT
    );
