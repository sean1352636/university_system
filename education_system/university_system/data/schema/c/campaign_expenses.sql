CREATE TABLE IF NOT EXISTS campaign_expenses (
            expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            amount REAL,
            description TEXT,
            receipt_path TEXT,
            expense_date TEXT,
            approved BOOLEAN DEFAULT 0,
            FOREIGN KEY (candidate_id) REFERENCES election_candidates (id)
        );
