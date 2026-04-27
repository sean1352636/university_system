CREATE TABLE IF NOT EXISTS collection_agencies (
            agency_id INTEGER PRIMARY KEY AUTOINCREMENT,
            agency_name TEXT NOT NULL,
            contact_email TEXT,
            contact_phone TEXT,
            commission_rate DECIMAL(5,2),
            minimum_amount DECIMAL(10,2),
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        );
