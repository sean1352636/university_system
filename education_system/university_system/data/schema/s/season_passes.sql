CREATE TABLE IF NOT EXISTS season_passes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pass_code TEXT UNIQUE NOT NULL,
            member_id INTEGER,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            pass_type TEXT NOT NULL,
            purchase_date TEXT DEFAULT CURRENT_TIMESTAMP,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            movies_used INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (member_id) REFERENCES members(id)
        );
