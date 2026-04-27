CREATE TABLE IF NOT EXISTS loyalty_bonus_points (
                        bonus_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id INTEGER,
                        points_awarded INTEGER NOT NULL,
                        reason TEXT NOT NULL,
                        description TEXT,
                        awarded_by TEXT,
                        award_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (customer_id) REFERENCES restaurant_customers(customer_id)
                    );
