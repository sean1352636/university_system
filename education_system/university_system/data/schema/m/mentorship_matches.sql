CREATE TABLE IF NOT EXISTS mentorship_matches (
            match_id INTEGER PRIMARY KEY AUTOINCREMENT,
            mentor_id INTEGER NOT NULL,
            mentee_student_id TEXT NOT NULL,
            match_date TEXT DEFAULT CURRENT_DATE,
            status TEXT DEFAULT 'active',
            meeting_frequency TEXT DEFAULT 'monthly',
            last_meeting_date TEXT,
            notes TEXT,
            FOREIGN KEY (mentor_id) REFERENCES alumni_mentors (mentor_id),
            FOREIGN KEY (mentee_student_id) REFERENCES students (student_id)
        );
