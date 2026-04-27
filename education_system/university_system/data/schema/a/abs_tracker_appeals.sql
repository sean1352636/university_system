CREATE TABLE IF NOT EXISTS abs_tracker_appeals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, request_id INTEGER, reason TEXT,
            status      TEXT DEFAULT 'open',
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
