CREATE TABLE IF NOT EXISTS adjustment_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    original_course TEXT,
                    requested_course TEXT,
                    reason TEXT,
                    current_grades TEXT,
                    status TEXT DEFAULT 'pending',
                    requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    decided_by TEXT,
                    decided_at TEXT
                );
