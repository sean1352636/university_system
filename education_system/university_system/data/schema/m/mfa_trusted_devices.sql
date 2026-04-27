CREATE TABLE IF NOT EXISTS mfa_trusted_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                device_id TEXT NOT NULL,  -- Unique device identifier
                device_name TEXT,
                device_fingerprint TEXT,  -- Browser/OS fingerprint
                ip_address TEXT,
                trust_token TEXT NOT NULL UNIQUE,  -- Secure token for verification
                is_trusted BOOLEAN DEFAULT 1,
                trusted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,  -- Trust expiration (default 30 days)
                last_used_at TIMESTAMP,
                revoked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, device_id)
            );
