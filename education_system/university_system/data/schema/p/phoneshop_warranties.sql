CREATE TABLE IF NOT EXISTS phoneshop_warranties (
        warranty_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_item_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        serial_number TEXT,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        warranty_type TEXT DEFAULT 'standard',
        status TEXT DEFAULT 'active',
        customer_id TEXT NOT NULL,
        FOREIGN KEY (order_item_id) REFERENCES phoneshop_order_items(item_id),
        FOREIGN KEY (product_id) REFERENCES phoneshop_products(product_id)
    );
