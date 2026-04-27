CREATE TABLE IF NOT EXISTS contract_amendments (
                    amendment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_id INTEGER NOT NULL,
                    change_type TEXT NOT NULL,
                    field_changed TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    effective_date TEXT NOT NULL,
                    reason TEXT,
                    approved_by TEXT,
                    approved_date TEXT,
                    status TEXT DEFAULT 'pending',
                    document_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (contract_id) REFERENCES staff_contracts(contract_id)
                );
