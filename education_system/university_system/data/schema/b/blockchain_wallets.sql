CREATE TABLE IF NOT EXISTS blockchain_wallets (
                wallet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                wallet_address TEXT NOT NULL UNIQUE,
                public_key TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "blockchain_type" TEXT DEFAULT 'ethereum',
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
