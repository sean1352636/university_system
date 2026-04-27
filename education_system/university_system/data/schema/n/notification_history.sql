CREATE TABLE IF NOT EXISTS notification_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notification_id INTEGER NOT NULL,
                    delivery_method TEXT NOT NULL,
                    delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'sent',
                    error_message TEXT,
                    FOREIGN KEY (notification_id) REFERENCES "notifications_old"(notification_id)
                );
