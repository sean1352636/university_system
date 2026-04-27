CREATE TABLE IF NOT EXISTS user_activity_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            activity_type TEXT,
            activity_description TEXT,
            timestamp TEXT,
            ip_address TEXT,
            user_agent TEXT
        );
