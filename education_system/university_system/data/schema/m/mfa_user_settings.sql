CREATE TABLE IF NOT EXISTS mfa_user_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        mfa_enabled INTEGER DEFAULT 0,
        backup_codes_generated INTEGER DEFAULT 0,
        enforcement_deadline TIMESTAMP,
        bypass_until TIMESTAMP,
        failed_attempts INTEGER DEFAULT 0,
        locked_until TIMESTAMP,
        last_successful_verification TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, verification_disabled BOOLEAN DEFAULT 0, mfa_status TEXT DEFAULT 'disabled' CHECK(mfa_status IN ('active', 'disabled')), disabled_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
