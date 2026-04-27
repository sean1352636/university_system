CREATE TABLE IF NOT EXISTS restaurant_mobile_orders (
            mobile_order_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            app_type TEXT NOT NULL,
            device_info TEXT,
            location_info TEXT,
            pickup_time TEXT,
            notification_sent INTEGER DEFAULT 0,
            FOREIGN KEY (order_id) REFERENCES orders (order_id)
        );
