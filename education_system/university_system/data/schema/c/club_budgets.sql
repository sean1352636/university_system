CREATE TABLE IF NOT EXISTS club_budgets (
            budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER,
            fiscal_year TEXT,
            total_budget REAL,
            allocated_budget REAL,
            spent_amount REAL DEFAULT 0.0,
            category TEXT,
            created_date TEXT,
            updated_date TEXT,
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
        );
