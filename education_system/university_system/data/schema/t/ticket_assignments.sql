CREATE TABLE IF NOT EXISTS ticket_assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            assigned_from INTEGER,
            assigned_to INTEGER,
            assignment_reason TEXT,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (assigned_from) REFERENCES users (id),
            FOREIGN KEY (assigned_to) REFERENCES users (id)
        );
