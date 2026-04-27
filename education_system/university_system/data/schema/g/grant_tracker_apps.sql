CREATE TABLE IF NOT EXISTS grant_tracker_apps (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                funding_body TEXT, principal_investigator TEXT, co_investigators TEXT,
                department TEXT, amount_requested REAL DEFAULT 0, amount_awarded REAL DEFAULT 0,
                status TEXT DEFAULT 'draft', deadline TEXT, submitted_at TEXT,
                decision_date TEXT, start_date TEXT, end_date TEXT, abstract TEXT,
                created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
