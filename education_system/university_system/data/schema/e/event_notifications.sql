CREATE TABLE IF NOT EXISTS event_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                user_id TEXT,
                notification_type TEXT NOT NULL,
                send_at TEXT NOT NULL,
                sent BOOLEAN DEFAULT 0,
                sent_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events (id)
            );
