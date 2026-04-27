CREATE TABLE IF NOT EXISTS communication_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                action_details TEXT,
                performed_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
