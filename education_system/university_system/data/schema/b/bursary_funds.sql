CREATE TABLE IF NOT EXISTS bursary_funds (
                    fund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    fund_type TEXT NOT NULL DEFAULT 'hardship',
                    total_budget REAL NOT NULL DEFAULT 0,
                    allocated REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );
