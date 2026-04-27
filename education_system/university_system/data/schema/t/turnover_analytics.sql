CREATE TABLE IF NOT EXISTS turnover_analytics (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    department TEXT,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    period_type TEXT DEFAULT 'monthly',
                    headcount_start INTEGER DEFAULT 0,
                    headcount_end INTEGER DEFAULT 0,
                    voluntary_exits INTEGER DEFAULT 0,
                    involuntary_exits INTEGER DEFAULT 0,
                    retirements INTEGER DEFAULT 0,
                    transfers_out INTEGER DEFAULT 0,
                    new_hires INTEGER DEFAULT 0,
                    transfers_in INTEGER DEFAULT 0,
                    turnover_rate REAL,
                    retention_rate REAL,
                    avg_tenure_months REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
