CREATE TABLE IF NOT EXISTS restaurant_customer_segments (
            segment_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            criteria TEXT NOT NULL,
            customer_count INTEGER DEFAULT 0,
            created_date TEXT,
            last_updated TEXT
        );
