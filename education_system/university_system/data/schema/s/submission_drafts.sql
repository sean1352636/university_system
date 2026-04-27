CREATE TABLE IF NOT EXISTS submission_drafts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assignment_id INTEGER NOT NULL,
                        student_id INTEGER NOT NULL,
                        content TEXT,
                        version INTEGER DEFAULT 1,
                        file_path TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
