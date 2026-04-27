CREATE TABLE IF NOT EXISTS health_advisories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            advisory_type TEXT,
            content TEXT,
            priority TEXT,
            target_audience TEXT,
            effective_date TEXT,
            expiry_date TEXT,
            issued_by TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT
        );
