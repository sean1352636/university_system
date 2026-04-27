CREATE TABLE IF NOT EXISTS ip_inventors (
                    inventor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    disclosure_id INTEGER,
                    patent_id INTEGER,
                    user_id TEXT NOT NULL,
                    contribution_percentage REAL DEFAULT 0,
                    is_primary INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (disclosure_id) REFERENCES ip_disclosures(disclosure_id),
                    FOREIGN KEY (patent_id) REFERENCES patents(patent_id)
                );
