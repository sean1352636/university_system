CREATE TABLE IF NOT EXISTS abs_tracker_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT, name TEXT, UNIQUE(module_code, name)
        );
