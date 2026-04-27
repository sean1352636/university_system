CREATE TABLE IF NOT EXISTS realtime_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    recipient_id INTEGER,
                    title TEXT NOT NULL,
                    message TEXT,
                    data TEXT,
                    priority INTEGER DEFAULT 2,
                    created_at TEXT NOT NULL,
                    read_at TEXT,
                    expires_at TEXT
                , "user_id" INTEGER, "notification_type" TEXT DEFAULT 'info', "is_read" INTEGER DEFAULT 0, "action_url" TEXT);
