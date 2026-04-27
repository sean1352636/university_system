CREATE TABLE IF NOT EXISTS club_competitions (
            competition_id INTEGER PRIMARY KEY AUTOINCREMENT,
            competition_name TEXT,
            description TEXT,
            competition_type TEXT,
            start_date TEXT,
            end_date TEXT,
            registration_deadline TEXT,
            max_participants_per_club INTEGER,
            prizes TEXT,
            status TEXT DEFAULT 'upcoming',
            organizer_id TEXT,
            FOREIGN KEY (organizer_id) REFERENCES students (student_id)
        );
