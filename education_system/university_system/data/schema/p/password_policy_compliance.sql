CREATE TABLE IF NOT EXISTS password_policy_compliance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                last_password_change TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                password_expires_at TIMESTAMP,
                must_change INTEGER DEFAULT 0, "failed_attempts" INTEGER DEFAULT 0, "locked_until" TEXT, "mfa_enabled" INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
