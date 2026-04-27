CREATE TABLE IF NOT EXISTS restaurant_orders (
                        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id INTEGER,
                        order_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                        total_price REAL,
                        tax_amount REAL,
                        status TEXT DEFAULT 'Pending',
                        payment_method TEXT
                    );
