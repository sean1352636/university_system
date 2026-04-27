CREATE TABLE IF NOT EXISTS abs_tracker_auto_excuse_rules (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            status     TEXT DEFAULT 'excused',
            enabled    INTEGER DEFAULT 1
        );
