CREATE TABLE IF NOT EXISTS restaurant_marketing_campaigns (
            campaign_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            target_audience TEXT,
            start_date TEXT,
            end_date TEXT,
            budget REAL DEFAULT 0,
            spent_amount REAL DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Draft',
            created_by TEXT,
            created_date TEXT
        );
