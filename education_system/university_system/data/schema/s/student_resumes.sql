CREATE TABLE IF NOT EXISTS student_resumes (
            resume_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            resume_name TEXT NOT NULL,
            file_url TEXT NOT NULL,
            template_used TEXT,
            is_primary BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
