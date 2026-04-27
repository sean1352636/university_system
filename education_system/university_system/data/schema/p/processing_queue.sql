CREATE TABLE IF NOT EXISTS processing_queue (
                id TEXT PRIMARY KEY,
                submission_data TEXT NOT NULL,
                priority INTEGER DEFAULT 1,
                status TEXT DEFAULT 'queued',
                created_at TEXT NOT NULL,
                processed_at TEXT
            );
