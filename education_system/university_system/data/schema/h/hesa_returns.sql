CREATE TABLE IF NOT EXISTS hesa_returns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    academic_year TEXT NOT NULL,
                    return_type TEXT NOT NULL,
                    status TEXT DEFAULT 'draft',
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    submitted_at TEXT,
                    xml_data TEXT,
                    notes TEXT
                );
