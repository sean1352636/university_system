CREATE TABLE IF NOT EXISTS customer_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER UNIQUE NOT NULL,
            avatar_url TEXT,
            favorite_genre TEXT,
            favorite_seats TEXT,
            preferred_snacks TEXT,
            notifications_email INTEGER DEFAULT 1,
            notifications_sms INTEGER DEFAULT 0,
            language_preference TEXT DEFAULT 'en',
            accessibility_needs TEXT,
            FOREIGN KEY (member_id) REFERENCES members(id)
        );
