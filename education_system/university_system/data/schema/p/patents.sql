CREATE TABLE IF NOT EXISTS patents (
                    patent_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    disclosure_id INTEGER,
                    patent_number TEXT,
                    title TEXT NOT NULL,
                    patent_office TEXT DEFAULT 'USPTO',
                    filing_date TEXT,
                    publication_date TEXT,
                    grant_date TEXT,
                    expiry_date TEXT,
                    status TEXT DEFAULT 'pending',
                    cost_to_date REAL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (disclosure_id) REFERENCES ip_disclosures(disclosure_id)
                );
