CREATE TABLE IF NOT EXISTS alumni_mentors (
            mentor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_student_id TEXT NOT NULL,
            job_title TEXT,
            company TEXT,
            industry TEXT,
            expertise_areas TEXT,
            max_mentees INTEGER DEFAULT 3,
            is_active BOOLEAN DEFAULT 1,
            bio TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
