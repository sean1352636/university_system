CREATE TABLE IF NOT EXISTS cinema_referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referral_code TEXT UNIQUE NOT NULL,
            referrer_email TEXT NOT NULL,
            referee_email TEXT,
            status TEXT DEFAULT 'pending',
            reward_given INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
