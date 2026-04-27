CREATE TABLE IF NOT EXISTS grocery_transaction_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            discount REAL DEFAULT 0,
            subtotal REAL NOT NULL,
            FOREIGN KEY (transaction_id) REFERENCES grocery_transactions (transaction_id),
            FOREIGN KEY (product_id) REFERENCES grocery_products (product_id)
        );
