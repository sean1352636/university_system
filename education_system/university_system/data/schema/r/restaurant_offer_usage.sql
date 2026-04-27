CREATE TABLE IF NOT EXISTS restaurant_offer_usage (
            usage_id TEXT PRIMARY KEY,
            offer_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            usage_date TEXT,
            discount_amount REAL,
            FOREIGN KEY (offer_id) REFERENCES restaurant_special_offers (offer_id),
            FOREIGN KEY (customer_id) REFERENCES restaurant_customers (customer_id),
            FOREIGN KEY (order_id) REFERENCES orders (order_id)
        );
