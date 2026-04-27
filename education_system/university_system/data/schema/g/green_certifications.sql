CREATE TABLE IF NOT EXISTS green_certifications (
                cert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_name TEXT,
                entity_type TEXT,
                certification_level TEXT,
                score REAL DEFAULT 0,
                awarded_date TEXT,
                expires_date TEXT,
                notes TEXT
            );
