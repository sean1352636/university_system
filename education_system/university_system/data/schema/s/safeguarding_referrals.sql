CREATE TABLE IF NOT EXISTS safeguarding_referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT, source_id INTEGER,
                    referred_by TEXT, referred_at TEXT,
                    reason TEXT, status TEXT DEFAULT 'open'
                );
