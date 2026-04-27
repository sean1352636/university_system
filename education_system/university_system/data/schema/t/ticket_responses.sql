CREATE TABLE IF NOT EXISTS ticket_responses (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            responder_id TEXT NOT NULL,
            responder_role TEXT NOT NULL,
            response_text TEXT NOT NULL,
            response_datetime TEXT NOT NULL,
            is_internal BOOLEAN DEFAULT 0,
            is_auto_generated BOOLEAN DEFAULT 0,
            template_used TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id)
        );
