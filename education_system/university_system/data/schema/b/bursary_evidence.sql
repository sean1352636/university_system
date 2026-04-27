CREATE TABLE IF NOT EXISTS bursary_evidence (
                    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    evidence_type TEXT NOT NULL,
                    filename TEXT,
                    description TEXT,
                    verified INTEGER NOT NULL DEFAULT 0,
                    verified_by TEXT,
                    verified_at TEXT,
                    uploaded_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (application_id) REFERENCES bursary_applications (application_id)
                );
