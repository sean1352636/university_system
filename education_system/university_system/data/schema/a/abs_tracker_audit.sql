CREATE TABLE IF NOT EXISTS abs_tracker_audit (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT DEFAULT CURRENT_TIMESTAMP,
            user_id     INTEGER,
            username    TEXT,
            action      TEXT,
            target      TEXT,
            target_id   TEXT,
            details     TEXT
        );
