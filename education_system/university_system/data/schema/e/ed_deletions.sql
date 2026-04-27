CREATE TABLE IF NOT EXISTS ed_deletions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        snapshot TEXT NOT NULL,
        requested_by TEXT NOT NULL,
        requested_at TEXT NOT NULL,
        approved_by TEXT,
        approved_at TEXT,
        status TEXT DEFAULT 'pending_restore',
        hard_deleted_at TEXT
    );
