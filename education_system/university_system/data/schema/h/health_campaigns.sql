CREATE TABLE IF NOT EXISTS health_campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_name TEXT,
                    campaign_type TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    target_population TEXT,
                    description TEXT,
                    goals TEXT,
                    status TEXT DEFAULT 'planned',
                    budget REAL,
                    created_by TEXT,
                    created_at TEXT
                );
