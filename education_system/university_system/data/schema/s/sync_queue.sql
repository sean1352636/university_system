CREATE TABLE IF NOT EXISTS sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                queue_name TEXT,        -- optional: 'default','labs','claims'
                entity_type TEXT,       -- e.g., 'student','claim','lab_order'
                entity_id TEXT,
                operation TEXT,         -- upsert/delete/sync
                payload TEXT,
                priority INTEGER DEFAULT 5,
                attempts INTEGER DEFAULT 0,
                next_attempt_at TEXT,
                last_error TEXT,
                status TEXT,            -- pending/locked/failed/done
                locked_by TEXT,
                locked_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            );
