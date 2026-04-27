CREATE TABLE IF NOT EXISTS tax_brackets (
                    bracket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tax_year TEXT NOT NULL,
                    bracket_name TEXT NOT NULL,
                    lower_limit REAL NOT NULL,
                    upper_limit REAL,
                    rate REAL NOT NULL,
                    personal_allowance REAL DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
