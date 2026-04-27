CREATE TABLE IF NOT EXISTS external_submissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assignment_id INTEGER NOT NULL,
                        student_id TEXT NOT NULL,
                        url TEXT NOT NULL,
                        link_type TEXT NOT NULL DEFAULT 'other',
                        is_validated INTEGER NOT NULL DEFAULT 0,
                        submitted_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );
