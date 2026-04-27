CREATE TABLE IF NOT EXISTS notification_actions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        notification_id INTEGER NOT NULL,
                        action_text TEXT NOT NULL,
                        action_url TEXT NOT NULL,
                        action_type TEXT DEFAULT 'link',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (notification_id) REFERENCES notifications(id)
                    );
