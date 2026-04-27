CREATE TABLE IF NOT EXISTS betting_accounts (
                    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    username TEXT NOT NULL,
                    email TEXT,
                    balance DECIMAL(10,2) DEFAULT 0.00,
                    total_deposited DECIMAL(10,2) DEFAULT 0.00,
                    total_withdrawn DECIMAL(10,2) DEFAULT 0.00,
                    total_wagered DECIMAL(10,2) DEFAULT 0.00,
                    total_won DECIMAL(10,2) DEFAULT 0.00,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
