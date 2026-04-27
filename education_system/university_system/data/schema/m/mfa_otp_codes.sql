CREATE TABLE IF NOT EXISTS mfa_otp_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                method_type TEXT NOT NULL CHECK(method_type IN ('sms', 'email')),
                code TEXT NOT NULL,
                code_hash TEXT NOT NULL,  -- Hashed version for secure comparison
                expires_at TIMESTAMP NOT NULL,
                is_used BOOLEAN DEFAULT 0,
                used_at TIMESTAMP,
                attempts INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
