CREATE TABLE IF NOT EXISTS restaurant_purchase_order_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit_of_measure TEXT,
                unit_cost REAL NOT NULL,
                total_cost REAL NOT NULL,
                received_quantity REAL DEFAULT 0,
                FOREIGN KEY (order_id) REFERENCES restaurant_purchase_orders(order_id) ON DELETE CASCADE
            );
