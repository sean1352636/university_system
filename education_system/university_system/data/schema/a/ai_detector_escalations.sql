CREATE TABLE IF NOT EXISTS ai_detector_escalations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    escalation_id TEXT UNIQUE NOT NULL,
                    submission_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    violation_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    recommended_action TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    escalated_by TEXT,
                    escalated_at TEXT NOT NULL,
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    resolution TEXT,
                    notes TEXT
                );
