CREATE TABLE IF NOT EXISTS user_preferences (
            user_id TEXT PRIMARY KEY,
            email_notifications BOOLEAN DEFAULT 1,
            in_app_notifications BOOLEAN DEFAULT 1,
            push_notifications BOOLEAN DEFAULT 1,
            digest_frequency TEXT DEFAULT 'daily',  -- immediate, daily, weekly
            theme TEXT DEFAULT 'light',
            language TEXT DEFAULT 'en',
            timezone TEXT DEFAULT 'UTC',
            preferences_json TEXT  -- Additional JSON preferences
        );
