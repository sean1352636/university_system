CREATE TABLE IF NOT EXISTS late_passes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        assignment_id INTEGER,
                        used INTEGER NOT NULL DEFAULT 0,
                        granted_by TEXT,
                        granted_at TEXT NOT NULL DEFAULT (datetime('now')),
                        reason TEXT
                    );
