CREATE TABLE IF NOT EXISTS sis_sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_type TEXT NOT NULL,
                    records_synced INTEGER DEFAULT 0,
                    records_failed INTEGER DEFAULT 0,
                    synced_by TEXT,
                    synced_at TEXT DEFAULT (datetime('now')),
                    details_json TEXT
                );
