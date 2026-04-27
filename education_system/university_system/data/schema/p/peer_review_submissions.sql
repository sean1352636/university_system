CREATE TABLE IF NOT EXISTS peer_review_submissions (
                    submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id INTEGER NOT NULL,
                    submitter_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    material_type TEXT DEFAULT 'other',
                    course_code TEXT,
                    file_path TEXT,
                    file_name TEXT,
                    version INTEGER DEFAULT 1,
                    parent_submission_id INTEGER,
                    status TEXT DEFAULT 'draft',
                    submitted_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cycle_id) REFERENCES peer_review_cycles(cycle_id),
                    FOREIGN KEY (parent_submission_id) REFERENCES peer_review_submissions(submission_id)
                );
