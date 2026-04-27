CREATE TABLE IF NOT EXISTS grade_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER,
                    student_id TEXT,
                    assignment_id INTEGER,
                    old_grade REAL,
                    new_grade REAL,
                    changed_by TEXT,
                    reason TEXT,
                    changed_at TEXT DEFAULT (datetime('now'))
                );
