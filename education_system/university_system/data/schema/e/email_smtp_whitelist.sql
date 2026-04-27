CREATE TABLE IF NOT EXISTS email_smtp_whitelist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_address TEXT NOT NULL UNIQUE,
                is_active BOOLEAN DEFAULT 1,
                added_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
