CREATE TABLE IF NOT EXISTS carrental_insurance (
                    insurance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    daily_rate DECIMAL(10,2) NOT NULL,
                    coverage_type TEXT,
                    max_coverage DECIMAL(10,2),
                    deductible DECIMAL(10,2) DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
