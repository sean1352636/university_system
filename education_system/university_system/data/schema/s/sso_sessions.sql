CREATE TABLE IF NOT EXISTS sso_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider_id TEXT NOT NULL,
                session_index TEXT,
                access_token_hash TEXT,
                token_expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (provider_id) REFERENCES sso_providers(provider_id) ON DELETE CASCADE
            );
