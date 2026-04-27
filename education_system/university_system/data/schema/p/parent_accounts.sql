CREATE TABLE IF NOT EXISTS parent_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id TEXT UNIQUE,
            first_name TEXT,
            last_name TEXT,
            email TEXT UNIQUE,
            phone TEXT,
            address TEXT,
            emergency_contact BOOLEAN DEFAULT 0,
            registration_date TEXT,
            two_factor_enabled BOOLEAN DEFAULT 0,
            two_factor_secret TEXT,
            profile_photo TEXT
        , "created_at" TEXT, "relationship" TEXT, "user_id" INTEGER, "verified" INTEGER DEFAULT 0);
