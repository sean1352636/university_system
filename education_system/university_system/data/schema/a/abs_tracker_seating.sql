CREATE TABLE IF NOT EXISTS abs_tracker_seating (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT, date TEXT, layout_json TEXT,
            UNIQUE(module_code, date)
        );
