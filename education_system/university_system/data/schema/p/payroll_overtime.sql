CREATE TABLE IF NOT EXISTS payroll_overtime (
                    overtime_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    hours REAL NOT NULL,
                    rate_multiplier REAL DEFAULT 1.5,
                    reason TEXT,
                    status TEXT DEFAULT 'pending',
                    approved_by TEXT,
                    approved_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
