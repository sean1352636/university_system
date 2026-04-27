CREATE TABLE IF NOT EXISTS union_trips (
            trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_name TEXT NOT NULL,
            destination TEXT NOT NULL,
            trip_date TEXT NOT NULL,
            return_date TEXT NOT NULL,
            description TEXT,
            max_participants INTEGER DEFAULT 30,
            estimated_cost REAL DEFAULT 0.0,
            organizer_club_id INTEGER,
            created_by TEXT,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'upcoming',
            FOREIGN KEY (organizer_club_id) REFERENCES student_clubs (club_id),
            CHECK (status IN ('upcoming', 'full', 'cancelled', 'completed'))
        );
