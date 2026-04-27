CREATE TABLE IF NOT EXISTS abs_tracker_trash (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            deleted_at     TEXT DEFAULT CURRENT_TIMESTAMP,
            deleted_by     TEXT,
            original_table TEXT,
            original_id    INTEGER,
            payload        TEXT
        );
