CREATE TABLE IF NOT EXISTS payroll_periods (
                    period_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    period_type TEXT NOT NULL DEFAULT 'monthly',
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    payment_date TEXT,
                    status TEXT DEFAULT 'draft',
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
