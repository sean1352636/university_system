CREATE TABLE IF NOT EXISTS ip_disclosures (
                    disclosure_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    ip_type TEXT DEFAULT 'invention',
                    development_stage TEXT DEFAULT 'concept',
                    funding_source TEXT,
                    department TEXT,
                    status TEXT DEFAULT 'draft',
                    submitted_date TEXT,
                    reviewed_by TEXT,
                    review_date TEXT,
                    review_comments TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
