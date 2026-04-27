CREATE TABLE IF NOT EXISTS mfa_methods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        method_type TEXT NOT NULL,
        is_enabled INTEGER DEFAULT 0,
        secret_key TEXT,
        phone_number TEXT,
        email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_used_at TIMESTAMP, method_identifier TEXT, is_primary BOOLEAN DEFAULT 0, setup_completed_at TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        UNIQUE(user_id, method_type)
    );
