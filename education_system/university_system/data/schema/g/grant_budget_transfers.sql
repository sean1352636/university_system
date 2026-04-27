CREATE TABLE IF NOT EXISTS grant_budget_transfers (
                    transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grant_application_id INTEGER NOT NULL,
                    from_allocation_id INTEGER NOT NULL,
                    to_allocation_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    reason TEXT,
                    status TEXT DEFAULT 'pending',
                    requested_by TEXT,
                    approved_by TEXT,
                    approved_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grant_application_id) REFERENCES grant_applications(grant_application_id),
                    FOREIGN KEY (from_allocation_id) REFERENCES grant_budget_allocations(allocation_id),
                    FOREIGN KEY (to_allocation_id) REFERENCES grant_budget_allocations(allocation_id)
                );
