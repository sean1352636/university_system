CREATE TABLE IF NOT EXISTS corporate_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            contact_phone TEXT,
            billing_address TEXT,
            tax_id TEXT,
            credit_limit REAL DEFAULT 1000,
            current_balance REAL DEFAULT 0,
            payment_terms INTEGER DEFAULT 30,
            discount_percent REAL DEFAULT 10,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
