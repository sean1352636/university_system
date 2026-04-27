CREATE TABLE IF NOT EXISTS ai_violation_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id TEXT,
                student_id TEXT,
                student_name TEXT,
                ai_score REAL,
                pushed_to TEXT,
                pushed_by TEXT,
                pushed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
