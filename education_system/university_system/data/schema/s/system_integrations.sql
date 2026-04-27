CREATE TABLE IF NOT EXISTS system_integrations (
            integration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,  -- sso, lms, sis, calendar, etc.
            config TEXT NOT NULL,  -- JSON configuration
            is_active BOOLEAN DEFAULT 0,
            last_sync_datetime TEXT,
            sync_status TEXT DEFAULT 'never',
            error_log TEXT
        );
