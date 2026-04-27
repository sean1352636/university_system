CREATE TABLE IF NOT EXISTS access_cards (
                card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_number TEXT UNIQUE NOT NULL,
                user_id TEXT,
                user_name TEXT,
                card_type TEXT DEFAULT 'staff',
                access_level TEXT,
                buildings_access TEXT,
                issue_date TEXT,
                expiry_date TEXT,
                status TEXT DEFAULT 'active',
                issued_by TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
