CREATE TABLE IF NOT EXISTS group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                group_type TEXT NOT NULL,
                group_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                content TEXT NOT NULL,
                attachment_path TEXT,
                sent_at TEXT NOT NULL,
                FOREIGN KEY (sender_id) REFERENCES users (id)
            );
