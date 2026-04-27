CREATE TABLE IF NOT EXISTS mentorships (
            mentorship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            mentor_id TEXT,
            mentee_id TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT,
            focus_area TEXT,
            notes TEXT,
            match_score REAL DEFAULT 0.0,
            meeting_frequency TEXT,
            communication_preference TEXT,
            goals TEXT,
            FOREIGN KEY (mentor_id) REFERENCES alumni (alumni_id)
        );
