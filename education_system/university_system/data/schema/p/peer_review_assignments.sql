CREATE TABLE IF NOT EXISTS peer_review_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id TEXT UNIQUE NOT NULL,
            session_id TEXT NOT NULL,
            reviewer_id TEXT NOT NULL,
            reviewee_id TEXT NOT NULL,
            submission_id INTEGER,
            due_date TIMESTAMP,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reviewer_id) REFERENCES students (student_id),
            FOREIGN KEY (reviewee_id) REFERENCES students (student_id),
            FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id)
        );
