CREATE TABLE IF NOT EXISTS feedback_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT,
                created_by INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id),
                FOREIGN KEY (created_by) REFERENCES users (id)
            );
