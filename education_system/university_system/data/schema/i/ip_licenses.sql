CREATE TABLE IF NOT EXISTS ip_licenses (
                    license_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patent_id INTEGER,
                    disclosure_id INTEGER,
                    licensee_name TEXT NOT NULL,
                    license_type TEXT DEFAULT 'non_exclusive',
                    royalty_rate REAL DEFAULT 0,
                    territory TEXT DEFAULT 'worldwide',
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    annual_fee REAL DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (patent_id) REFERENCES patents(patent_id),
                    FOREIGN KEY (disclosure_id) REFERENCES ip_disclosures(disclosure_id)
                );
