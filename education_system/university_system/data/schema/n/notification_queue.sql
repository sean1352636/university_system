CREATE TABLE IF NOT EXISTS notification_queue (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    event_id TEXT,
                    notification_type TEXT NOT NULL,
                    scheduled_time TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    message TEXT,
                    date_added TEXT NOT NULL,
                    sent_at TEXT,
                    FOREIGN KEY (event_id) REFERENCES "academic_calendar_events" (id) ON DELETE CASCADE
                );
