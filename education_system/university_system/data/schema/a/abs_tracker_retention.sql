CREATE TABLE IF NOT EXISTS abs_tracker_retention (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            policy     TEXT,
            years      INTEGER,
            applied_at TEXT
        );
