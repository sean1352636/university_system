CREATE TABLE IF NOT EXISTS expense_policies (
                    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    max_daily_amount REAL,
                    max_single_claim REAL,
                    requires_pre_approval_above REAL,
                    mileage_rate REAL DEFAULT 0.45,
                    subsistence_rate REAL,
                    applies_to_roles TEXT,
                    effective_from TEXT,
                    effective_to TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
