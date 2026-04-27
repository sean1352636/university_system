CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phone TEXT,
            points INTEGER DEFAULT 0,
            tier TEXT DEFAULT 'Bronze',
            total_spent REAL DEFAULT 0,
            bookings_count INTEGER DEFAULT 0,
            join_date TEXT DEFAULT CURRENT_TIMESTAMP,
            birthday TEXT,
            preferences TEXT,
            status TEXT DEFAULT 'active'
        , referral_code TEXT, credit_balance REAL DEFAULT 0, favorite_seats TEXT, avatar TEXT);
