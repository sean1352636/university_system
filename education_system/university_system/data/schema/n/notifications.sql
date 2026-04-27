CREATE TABLE IF NOT EXISTS notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    source_system TEXT,
                    source_id TEXT,
                    is_read INTEGER DEFAULT 0,
                    is_archived INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    read_at TEXT,
                    expires_at TEXT,
                    metadata TEXT, [assignment_id] INTEGER, [recipient_type] TEXT, [recipient_id] TEXT, [notification_type] TEXT DEFAULT "info", [sent] BOOLEAN DEFAULT 0, [created_date] DATETIME, "related_ticket_id" INTEGER, "created_datetime" TEXT, "read_datetime" TEXT, "data" TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(username)
                );
