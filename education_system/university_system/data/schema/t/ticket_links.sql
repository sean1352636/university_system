CREATE TABLE IF NOT EXISTS ticket_links (
            link_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            linked_ticket_id INTEGER,
            link_type TEXT,
            created_by INTEGER,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (linked_ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        );
