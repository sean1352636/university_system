CREATE TABLE IF NOT EXISTS abs_tracker_note_requests (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id TEXT, module_code TEXT, date TEXT,
            status       TEXT DEFAULT 'open',
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            fulfiller_id TEXT
        );
