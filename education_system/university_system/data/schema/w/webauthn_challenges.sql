CREATE TABLE IF NOT EXISTS webauthn_challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                challenge TEXT UNIQUE NOT NULL,
                session_id TEXT NOT NULL,
                challenge_type TEXT NOT NULL CHECK(challenge_type IN ('registration', 'authentication')),
                user_id INTEGER,
                expires_at TIMESTAMP NOT NULL,
                is_used BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
