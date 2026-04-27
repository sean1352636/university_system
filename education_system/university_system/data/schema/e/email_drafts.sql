CREATE TABLE IF NOT EXISTS email_drafts (
                    draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipients TEXT,
                    cc TEXT,
                    subject TEXT,
                    body TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
