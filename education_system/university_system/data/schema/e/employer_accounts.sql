CREATE TABLE IF NOT EXISTS employer_accounts (
                    employer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT NOT NULL UNIQUE,
                    contact_name TEXT,
                    contact_email TEXT,
                    contact_phone TEXT,
                    address TEXT,
                    sector TEXT,
                    company_size TEXT DEFAULT 'small',
                    portal_access_enabled INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    notes TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );
