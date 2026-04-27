CREATE TABLE IF NOT EXISTS ticket_escalations (
            escalation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            escalation_level INTEGER,
            escalated_to INTEGER,
            escalated_by INTEGER,
            escalation_reason TEXT,
            resolved BOOLEAN DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (escalated_to) REFERENCES users (id),
            FOREIGN KEY (escalated_by) REFERENCES users (id)
        );
