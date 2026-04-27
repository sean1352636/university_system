CREATE TABLE IF NOT EXISTS staff_mentors (
                    mentor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    programme_id INTEGER NOT NULL,
                    expertise_areas TEXT,
                    max_mentees INTEGER DEFAULT 3,
                    current_mentees INTEGER DEFAULT 0,
                    availability TEXT DEFAULT 'available',
                    bio TEXT,
                    status TEXT DEFAULT 'active',
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (programme_id) REFERENCES staff_mentoring_programmes(programme_id)
                );
