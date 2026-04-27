CREATE TABLE IF NOT EXISTS abs_tracker_request_comments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            author     TEXT,
            body       TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
