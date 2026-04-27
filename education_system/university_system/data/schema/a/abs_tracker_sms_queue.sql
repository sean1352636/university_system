CREATE TABLE IF NOT EXISTS abs_tracker_sms_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT, body TEXT,
                    queued_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'queued');
