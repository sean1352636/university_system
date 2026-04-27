CREATE TABLE IF NOT EXISTS grade_disputes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER,
                    student_id TEXT NOT NULL,
                    assignment_id INTEGER NOT NULL,
                    original_grade REAL,
                    requested_action TEXT,
                    reason TEXT NOT NULL,
                    evidence_path TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    reviewer_id TEXT,
                    reviewer_comments TEXT,
                    new_grade REAL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                );
