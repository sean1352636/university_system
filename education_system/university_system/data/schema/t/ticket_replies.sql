CREATE TABLE IF NOT EXISTS ticket_replies (
            reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            user_id INTEGER,
            message TEXT NOT NULL,
            is_internal BOOLEAN DEFAULT 0,
            reply_type TEXT DEFAULT 'comment',
            time_spent REAL DEFAULT 0,
            created_at TEXT,
            edited_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
