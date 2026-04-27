CREATE TABLE IF NOT EXISTS grant_tracker_budget (
                id INTEGER PRIMARY KEY AUTOINCREMENT, grant_id INTEGER NOT NULL,
                category TEXT DEFAULT 'other', description TEXT, amount REAL DEFAULT 0,
                is_approved INTEGER DEFAULT 0,
                FOREIGN KEY (grant_id) REFERENCES grant_tracker_apps(id));
