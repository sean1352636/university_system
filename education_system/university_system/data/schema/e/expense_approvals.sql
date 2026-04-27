CREATE TABLE IF NOT EXISTS expense_approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id INTEGER NOT NULL,
                    approver_id TEXT NOT NULL,
                    approval_level INTEGER DEFAULT 1,
                    decision TEXT,
                    comments TEXT,
                    decision_date TEXT,
                    amount_approved REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (claim_id) REFERENCES expense_claims(claim_id)
                );
