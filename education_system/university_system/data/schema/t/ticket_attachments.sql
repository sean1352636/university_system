CREATE TABLE IF NOT EXISTS ticket_attachments (
            attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_type TEXT NOT NULL,
            mime_type TEXT,
            uploaded_by TEXT NOT NULL,
            uploaded_datetime TEXT NOT NULL,
            is_public BOOLEAN DEFAULT 0,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id)
        );
