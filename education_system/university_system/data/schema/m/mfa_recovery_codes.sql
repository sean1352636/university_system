CREATE TABLE IF NOT EXISTS mfa_recovery_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code_hash TEXT NOT NULL,  -- Hashed recovery code
                is_used BOOLEAN DEFAULT 0,
                used_at TIMESTAMP,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,  -- Optional expiration
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
