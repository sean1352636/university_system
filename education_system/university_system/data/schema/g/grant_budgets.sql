CREATE TABLE IF NOT EXISTS grant_budgets (
            budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            requested_amount REAL NOT NULL,
            approved_amount REAL,
            spent_amount REAL DEFAULT 0,
            remaining_amount REAL,
            FOREIGN KEY (application_id) REFERENCES grant_applications (application_id)
        );
