CREATE TABLE IF NOT EXISTS file_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                version_number INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_current INTEGER DEFAULT 0,
                FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id)
            );
