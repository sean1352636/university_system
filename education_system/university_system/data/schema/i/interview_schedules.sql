CREATE TABLE IF NOT EXISTS interview_schedules (
            interview_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            interview_type TEXT NOT NULL,
            interview_date TEXT NOT NULL,
            interview_time TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 60,
            location TEXT,
            interviewer_name TEXT,
            meeting_link TEXT,
            status TEXT DEFAULT 'scheduled',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id) REFERENCES job_applications (application_id)
        );
