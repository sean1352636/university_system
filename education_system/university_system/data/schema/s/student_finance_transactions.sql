CREATE TABLE IF NOT EXISTS student_finance_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            balance_before DECIMAL(10,2),
            balance_after DECIMAL(10,2),
            description TEXT,
            reference_id TEXT,
            processed_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES student_finance_accounts(account_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        );
