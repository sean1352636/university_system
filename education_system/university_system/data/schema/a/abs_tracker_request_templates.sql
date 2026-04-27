CREATE TABLE IF NOT EXISTS abs_tracker_request_templates (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT UNIQUE,
            body    TEXT
        );
