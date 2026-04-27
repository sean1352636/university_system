CREATE TABLE IF NOT EXISTS fundraising_campaigns (
            campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_name TEXT,
            description TEXT,
            goal_amount REAL,
            current_amount REAL DEFAULT 0.0,
            start_date TEXT,
            end_date TEXT,
            created_by TEXT,
            created_date TEXT,
            status TEXT DEFAULT 'active',
            category TEXT,
            is_featured BOOLEAN DEFAULT 0
        );
