CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                session_token TEXT UNIQUE,
                ip_address TEXT,
                location TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_active INTEGER DEFAULT 1, session_id_hash TEXT, device_fingerprint TEXT, terminated_at TIMESTAMP, termination_reason TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
