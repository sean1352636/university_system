CREATE TABLE IF NOT EXISTS mfa_verification_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                method_type TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                failure_reason TEXT,
                ip_address TEXT,
                user_agent TEXT,
                device_id TEXT,
                attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
