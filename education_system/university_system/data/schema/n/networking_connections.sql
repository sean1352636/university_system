CREATE TABLE IF NOT EXISTS networking_connections (
            connection_id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id TEXT,
            recipient_id TEXT,
            connection_date TEXT,
            status TEXT DEFAULT 'pending',
            message TEXT,
            FOREIGN KEY (requester_id) REFERENCES alumni (alumni_id),
            FOREIGN KEY (recipient_id) REFERENCES alumni (alumni_id)
        );
