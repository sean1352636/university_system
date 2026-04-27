CREATE TABLE IF NOT EXISTS tour_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tour_id INTEGER NOT NULL,
            prospect_id INTEGER NOT NULL,
            num_guests INTEGER DEFAULT 0,
            registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            attended BOOLEAN DEFAULT 0,
            feedback TEXT,
            FOREIGN KEY (tour_id) REFERENCES campus_tours (tour_id),
            FOREIGN KEY (prospect_id) REFERENCES admission_prospects (prospect_id)
        );
