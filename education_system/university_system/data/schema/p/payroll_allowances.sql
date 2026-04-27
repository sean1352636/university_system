CREATE TABLE IF NOT EXISTS payroll_allowances (
                    allowance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    allowance_type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    frequency TEXT DEFAULT 'monthly',
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    is_active INTEGER DEFAULT 1,
                    approved_by TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
