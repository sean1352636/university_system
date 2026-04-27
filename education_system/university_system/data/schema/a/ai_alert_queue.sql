CREATE TABLE IF NOT EXISTS ai_alert_queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        student_name TEXT,
                        assignment_name TEXT,
                        risk_level TEXT,
                        ai_score REAL,
                        submission_id TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        dismissed_at TIMESTAMP,
                        dismiss_reason TEXT
                    );
