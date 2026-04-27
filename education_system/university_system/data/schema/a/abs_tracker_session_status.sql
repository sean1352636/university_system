CREATE TABLE IF NOT EXISTS abs_tracker_session_status (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT, date TEXT, status TEXT,
            set_by      INTEGER, set_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(module_code, date)
        );
