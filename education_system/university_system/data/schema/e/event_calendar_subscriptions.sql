CREATE TABLE IF NOT EXISTS event_calendar_subscriptions (
            subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            calendar_feed_url TEXT NOT NULL,
            filter_categories TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
