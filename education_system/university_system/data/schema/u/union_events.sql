CREATE TABLE IF NOT EXISTS union_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT NOT NULL,
                    description TEXT,
                    organizer_id INTEGER,
                    event_date TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    location TEXT,
                    category TEXT,
                    max_attendees INTEGER,
                    current_attendees INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'upcoming',
                    created_at TEXT,
                    FOREIGN KEY (organizer_id) REFERENCES student_clubs (club_id)
                );
