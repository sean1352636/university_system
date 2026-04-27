CREATE TABLE IF NOT EXISTS sabbatical_eligibility (
                    eligibility_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL UNIQUE,
                    years_of_service REAL DEFAULT 0,
                    last_sabbatical_end TEXT,
                    next_eligible_date TEXT,
                    is_eligible INTEGER DEFAULT 0,
                    notes TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
