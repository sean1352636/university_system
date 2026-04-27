CREATE TABLE IF NOT EXISTS mentorship_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            relationship_id INTEGER,
            session_date TEXT,
            duration_minutes INTEGER,
            notes TEXT,
            mentor_feedback TEXT,
            mentee_feedback TEXT,
            progress_rating INTEGER,
            FOREIGN KEY (relationship_id) REFERENCES mentorship_relationships (relationship_id)
        );
