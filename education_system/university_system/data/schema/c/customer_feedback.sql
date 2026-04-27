CREATE TABLE IF NOT EXISTS customer_feedback (
                    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER,
                    customer_name TEXT,
                    order_id INTEGER,
                    rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                    category TEXT,
                    feedback_text TEXT NOT NULL,
                    response TEXT,
                    responded_by TEXT,
                    response_date DATETIME,
                    status TEXT DEFAULT 'Pending',
                    feedback_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES restaurant_customers(customer_id),
                    FOREIGN KEY (order_id) REFERENCES orders(order_id)
                );
