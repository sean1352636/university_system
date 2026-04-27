CREATE TABLE IF NOT EXISTS student_review_flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                submission_id INTEGER,
                reason TEXT NOT NULL,
                severity TEXT NOT NULL,
                flagged_by TEXT,
                flagged_at TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                resolved_at TEXT,
                resolved_by TEXT,
                resolution_notes TEXT
            );
