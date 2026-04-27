CREATE TABLE IF NOT EXISTS digests (
                    digest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    digest_date DATE NOT NULL,
                    sent_at TIMESTAMP,
                    notification_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, digest_date),
                    FOREIGN KEY (user_id) REFERENCES users(username)
                );
