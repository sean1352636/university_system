CREATE TABLE IF NOT EXISTS budget_plans (
            budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_name TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            currency TEXT DEFAULT 'GBP',
            status TEXT DEFAULT 'draft', -- draft, approved, active, closed
            total_revenue_budget DECIMAL(12,2) DEFAULT 0,
            total_expense_budget DECIMAL(12,2) DEFAULT 0,
            created_by TEXT,
            approved_by TEXT,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT
        );
