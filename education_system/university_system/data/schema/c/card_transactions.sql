CREATE TABLE IF NOT EXISTS card_transactions (
                            transaction_id TEXT PRIMARY KEY,
                            order_id INTEGER,
                            card_type TEXT,
                            card_last4 TEXT,
                            amount REAL,
                            authorization_code TEXT,
                            transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (order_id) REFERENCES orders(order_id)
                        );
