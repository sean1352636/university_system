CREATE TABLE IF NOT EXISTS class_reunions (
            reunion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            graduation_year INTEGER,
            reunion_date TEXT,
            location TEXT,
            organizer_id TEXT,
            description TEXT,
            registration_fee REAL DEFAULT 0.0,
            max_attendees INTEGER,
            created_date TEXT,
            FOREIGN KEY (organizer_id) REFERENCES alumni (alumni_id)
        );
