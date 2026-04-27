CREATE TABLE IF NOT EXISTS admission_prospects (
            prospect_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            date_of_birth TEXT,
            country TEXT,
            state TEXT,
            city TEXT,
            high_school TEXT,
            intended_major TEXT,
            source TEXT,
            status TEXT DEFAULT 'prospect',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_contact_date TEXT
        );
