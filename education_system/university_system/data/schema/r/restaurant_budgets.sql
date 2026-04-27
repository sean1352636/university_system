CREATE TABLE IF NOT EXISTS restaurant_budgets (
            budget_id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            allocated_amount REAL NOT NULL,
            spent_amount REAL DEFAULT 0,
            created_date TEXT,
            created_by TEXT,
            notes TEXT
        );
