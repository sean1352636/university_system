CREATE TABLE IF NOT EXISTS abs_tracker_session_qr (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT, date TEXT, code TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(module_code, date)
        );
