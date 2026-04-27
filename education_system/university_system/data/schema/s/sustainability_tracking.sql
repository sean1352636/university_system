CREATE TABLE IF NOT EXISTS sustainability_tracking (
            tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            club_id INTEGER,
            carbon_footprint REAL,
            waste_generated REAL,
            waste_recycled REAL,
            transport_method TEXT,
            sustainability_score REAL,
            notes TEXT,
            recorded_date TEXT,
            FOREIGN KEY (event_id) REFERENCES union_events (event_id),
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
        );
