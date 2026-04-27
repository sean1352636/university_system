CREATE TABLE IF NOT EXISTS prediction_markets (
                    market_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT NOT NULL,
                    outcome_a TEXT NOT NULL,
                    outcome_b TEXT NOT NULL,
                    probability_a DECIMAL(5,2) DEFAULT 50.00,
                    probability_b DECIMAL(5,2) DEFAULT 50.00,
                    total_pool DECIMAL(10,2) DEFAULT 0.00,
                    pool_a DECIMAL(10,2) DEFAULT 0.00,
                    pool_b DECIMAL(10,2) DEFAULT 0.00,
                    resolution_date TEXT NOT NULL,
                    status TEXT DEFAULT 'open',
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT
                );
