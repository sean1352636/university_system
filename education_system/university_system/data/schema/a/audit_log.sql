CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT NOT NULL,
            table_name TEXT,
            record_id TEXT,
            old_values TEXT, -- JSON
            new_values TEXT, -- JSON
            ip_address TEXT,
            user_agent TEXT,
            session_id TEXT,
            timestamp TEXT NOT NULL
        , accommodation_id INTEGER, details TEXT);
