CREATE TABLE IF NOT EXISTS data_retention (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_type TEXT NOT NULL,
                retention_period INTEGER NOT NULL,
                deletion_date TEXT,
                status TEXT DEFAULT 'active'
            );
