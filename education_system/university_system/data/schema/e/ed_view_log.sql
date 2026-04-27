CREATE TABLE IF NOT EXISTS ed_view_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        viewer TEXT NOT NULL,
        viewed_at TEXT NOT NULL
    );
