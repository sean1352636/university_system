CREATE TABLE IF NOT EXISTS chat_room_invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            invited_by INTEGER NOT NULL,
            invited_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            responded_at TEXT,
            FOREIGN KEY (room_id) REFERENCES chat_rooms (id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (invited_by) REFERENCES users (id)
        );
