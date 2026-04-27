CREATE TABLE IF NOT EXISTS barber_gift_cards (
                gift_card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                initial_amount DECIMAL(10,2) NOT NULL,
                current_balance DECIMAL(10,2) NOT NULL,
                purchased_by TEXT,
                recipient_name TEXT,
                recipient_email TEXT,
                message TEXT,
                is_redeemed INTEGER DEFAULT 0,
                redeemed_at TEXT,
                expires_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
