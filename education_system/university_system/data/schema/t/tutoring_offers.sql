CREATE TABLE IF NOT EXISTS tutoring_offers (
            offer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tutor_id TEXT,
            subject TEXT,
            topic TEXT,
            hourly_rate REAL,
            availability TEXT,
            experience_level TEXT,
            description TEXT,
            rating REAL DEFAULT 0.0,
            total_sessions INTEGER DEFAULT 0,
            status TEXT DEFAULT 'available',
            FOREIGN KEY (tutor_id) REFERENCES students (student_id)
        );
