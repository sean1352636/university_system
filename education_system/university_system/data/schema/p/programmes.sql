CREATE TABLE IF NOT EXISTS programmes (
                    programme_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    level TEXT NOT NULL DEFAULT 'undergraduate',
                    department TEXT,
                    total_credits INTEGER DEFAULT 360,
                    duration_years INTEGER DEFAULT 3,
                    description TEXT,
                    status TEXT DEFAULT 'draft',
                    created_by TEXT,
                    approved_by TEXT,
                    approved_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
