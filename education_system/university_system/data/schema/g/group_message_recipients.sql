CREATE TABLE IF NOT EXISTS group_message_recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                is_read INTEGER DEFAULT 0,
                is_archived INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0,
                read_at TEXT,
                FOREIGN KEY (message_id) REFERENCES group_messages (id),
                FOREIGN KEY (recipient_id) REFERENCES users (id)
            );
