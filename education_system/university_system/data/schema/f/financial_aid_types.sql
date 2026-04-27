CREATE TABLE IF NOT EXISTS financial_aid_types (
            aid_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            aid_name TEXT NOT NULL,
            aid_category TEXT, -- 'grant', 'loan', 'work_study', 'emergency'
            description TEXT,
            max_amount DECIMAL(10,2),
            eligibility_criteria TEXT,
            application_deadline TEXT,
            is_renewable BOOLEAN DEFAULT 0,
            requires_repayment BOOLEAN DEFAULT 0,
            interest_rate DECIMAL(5,2),
            grace_period_months INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        );
