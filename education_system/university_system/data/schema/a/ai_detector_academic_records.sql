CREATE TABLE IF NOT EXISTS ai_detector_academic_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT UNIQUE NOT NULL,
                    student_id TEXT NOT NULL,
                    submission_id TEXT NOT NULL,
                    violation_type TEXT NOT NULL,
                    sanction TEXT NOT NULL,
                    sanction_details TEXT,
                    notes TEXT,
                    reviewer_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    synced_to_external INTEGER DEFAULT 0,
                    synced_at TEXT
                );
