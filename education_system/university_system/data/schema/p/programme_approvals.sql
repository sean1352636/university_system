CREATE TABLE IF NOT EXISTS programme_approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    programme_id INTEGER NOT NULL,
                    approval_level TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    comments TEXT,
                    reviewed_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id)
                );
