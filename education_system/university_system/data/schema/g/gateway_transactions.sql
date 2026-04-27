CREATE TABLE IF NOT EXISTS gateway_transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payment_id INTEGER,
                    gateway_id INTEGER NOT NULL,
                    gateway_transaction_id TEXT NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL,
                    gateway_fee DECIMAL(10,2),
                    raw_response TEXT, -- JSON response from gateway
                    webhook_verified BOOLEAN DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (payment_id) REFERENCES payments (payment_id),
                    FOREIGN KEY (gateway_id) REFERENCES payment_gateways (gateway_id)
                );
