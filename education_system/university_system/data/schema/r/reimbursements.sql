CREATE TABLE IF NOT EXISTS reimbursements (
                    reimbursement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'GBP',
                    payment_date TEXT,
                    payment_method TEXT,
                    reference_number TEXT,
                    bank_account_last4 TEXT,
                    status TEXT DEFAULT 'pending',
                    processed_by TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (claim_id) REFERENCES expense_claims(claim_id)
                );
