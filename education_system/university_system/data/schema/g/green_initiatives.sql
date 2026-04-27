CREATE TABLE IF NOT EXISTS green_initiatives (
                initiative_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                status TEXT DEFAULT 'active',
                created_by TEXT,
                created_date TEXT,
                target_date TEXT,
                carbon_target REAL,
                notes TEXT
            );
