CREATE TABLE IF NOT EXISTS order_discounts (
                                discount_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                order_id INTEGER,
                                discount_amount REAL,
                                discount_type TEXT,
                                discount_value REAL,
                                promo_code TEXT,
                                reason TEXT,
                                manager_approved BOOLEAN,
                                discount_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (order_id) REFERENCES orders(order_id)
                            );
