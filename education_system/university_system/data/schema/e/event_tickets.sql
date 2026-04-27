CREATE TABLE IF NOT EXISTS event_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            ticket_type TEXT,
            price REAL,
            quantity_available INTEGER,
            quantity_sold INTEGER DEFAULT 0,
            student_id TEXT,
            purchase_date TEXT,
            payment_status TEXT DEFAULT 'pending',
            FOREIGN KEY (event_id) REFERENCES union_events (event_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
