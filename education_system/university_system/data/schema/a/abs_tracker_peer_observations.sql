CREATE TABLE IF NOT EXISTS abs_tracker_peer_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            observer_id INTEGER, subject_id INTEGER, module_code TEXT,
            date TEXT, notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
