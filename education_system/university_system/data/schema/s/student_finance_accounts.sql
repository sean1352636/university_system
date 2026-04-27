CREATE TABLE IF NOT EXISTS student_finance_accounts (
    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT UNIQUE NOT NULL,
    balance DECIMAL(10,2) DEFAULT 0.00,
    currency TEXT DEFAULT 'GBP',
    account_status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
