CREATE TABLE IF NOT EXISTS restaurant_notifications (
            notification_id TEXT PRIMARY KEY,
            user_id TEXT,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            created_date TEXT NOT NULL,
            read_date TEXT,
            priority TEXT DEFAULT 'Normal',
            category TEXT,
            action_required INTEGER DEFAULT 0
        );
