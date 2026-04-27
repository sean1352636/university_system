CREATE TABLE IF NOT EXISTS abs_tracker_ta_handoff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER, ta_id INTEGER, module_code TEXT, note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
