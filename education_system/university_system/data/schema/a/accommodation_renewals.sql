CREATE TABLE IF NOT EXISTS accommodation_renewals (
                    renewal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    accommodation_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    renewal_request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    processed_date TIMESTAMP,
                    processed_by TEXT,
                    notes TEXT,
                    FOREIGN KEY (accommodation_id) REFERENCES accommodations(accommodation_id)
                );
