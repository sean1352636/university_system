CREATE TABLE IF NOT EXISTS abs_tracker_staff_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER, task TEXT, done INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            done_at TEXT
        );
