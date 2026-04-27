CREATE TABLE IF NOT EXISTS grant_budget_allocations (
                    allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grant_application_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    allocated_amount REAL DEFAULT 0,
                    spent_amount REAL DEFAULT 0,
                    committed_amount REAL DEFAULT 0,
                    remaining_amount REAL DEFAULT 0,
                    alert_threshold_pct REAL DEFAULT 80,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grant_application_id) REFERENCES grant_applications(grant_application_id),
                    FOREIGN KEY (category_id) REFERENCES grant_budget_categories(category_id)
                );
