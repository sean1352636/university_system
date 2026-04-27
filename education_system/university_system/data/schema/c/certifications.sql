CREATE TABLE IF NOT EXISTS certifications (
                    cert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    issuing_body TEXT,
                    credential_id TEXT,
                    issue_date TEXT,
                    expiry_date TEXT,
                    document_path TEXT,
                    status TEXT DEFAULT 'active',
                    reminder_sent BOOLEAN DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
