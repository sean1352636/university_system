CREATE TABLE IF NOT EXISTS barber_customer_notes (
                note_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                note TEXT NOT NULL,
                note_type TEXT DEFAULT 'general',
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
