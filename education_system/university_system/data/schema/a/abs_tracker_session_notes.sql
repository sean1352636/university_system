CREATE TABLE IF NOT EXISTS abs_tracker_session_notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id   INTEGER, module_code TEXT, date TEXT, note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
