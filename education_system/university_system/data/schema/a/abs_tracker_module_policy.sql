CREATE TABLE IF NOT EXISTS abs_tracker_module_policy (
            module_code      TEXT PRIMARY KEY,
            min_percent      REAL,
            late_as_absent   INTEGER,
            grace_minutes    INTEGER,
            notes            TEXT
        );
