CREATE TABLE IF NOT EXISTS ai_detector_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    submission_title TEXT,
                    risk_level TEXT NOT NULL,
                    ai_score REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    reviewed_by TEXT,
                    dismissal_reason TEXT,
                    notes TEXT
                );
