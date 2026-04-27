CREATE TABLE IF NOT EXISTS chat_rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                room_type TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1, max_members INTEGER DEFAULT 50,
                FOREIGN KEY (created_by) REFERENCES users (id)
            );
