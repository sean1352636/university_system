CREATE TABLE IF NOT EXISTS campus_tours (
            tour_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tour_date TEXT NOT NULL,
            tour_time TEXT NOT NULL,
            tour_guide TEXT,
            max_attendees INTEGER DEFAULT 20,
            current_attendees INTEGER DEFAULT 0,
            meeting_point TEXT,
            duration_minutes INTEGER DEFAULT 90,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
