CREATE TABLE IF NOT EXISTS ticket_time_tracking (
            time_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            user_id INTEGER,
            start_time TEXT,
            end_time TEXT,
            duration_minutes INTEGER,
            description TEXT,
            billable BOOLEAN DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
