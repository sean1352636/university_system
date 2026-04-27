CREATE TABLE IF NOT EXISTS barber_no_shows (
                no_show_id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER NOT NULL,
                customer_id TEXT NOT NULL,
                marked_by TEXT,
                added_to_watchlist INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (appointment_id) REFERENCES barber_appointments(appointment_id)
            );
