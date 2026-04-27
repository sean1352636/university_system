CREATE TABLE IF NOT EXISTS employers (
            employer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            industry TEXT,
            company_size TEXT,
            website TEXT,
            contact_person TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            description TEXT,
            logo_url TEXT,
            is_verified BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
