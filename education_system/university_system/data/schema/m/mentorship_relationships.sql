CREATE TABLE IF NOT EXISTS mentorship_relationships (
            relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            mentor_id TEXT,
            mentee_id TEXT,
            skill_area TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'active',
            mentor_rating REAL,
            mentee_rating REAL,
            notes TEXT,
            FOREIGN KEY (mentor_id) REFERENCES students (student_id),
            FOREIGN KEY (mentee_id) REFERENCES students (student_id)
        );
