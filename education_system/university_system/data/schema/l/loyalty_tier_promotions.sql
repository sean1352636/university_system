CREATE TABLE IF NOT EXISTS loyalty_tier_promotions (
                        promotion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id INTEGER NOT NULL,
                        old_tier TEXT NOT NULL,
                        new_tier TEXT NOT NULL,
                        reason TEXT,
                        notes TEXT,
                        promoted_by TEXT,
                        promotion_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (customer_id) REFERENCES restaurant_customers(customer_id)
                    );
