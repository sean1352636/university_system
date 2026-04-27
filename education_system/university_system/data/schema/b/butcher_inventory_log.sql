CREATE TABLE IF NOT EXISTS butcher_inventory_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                change_type TEXT NOT NULL,
                quantity_change DECIMAL(10,2) NOT NULL,
                previous_quantity DECIMAL(10,2),
                new_quantity DECIMAL(10,2),
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                FOREIGN KEY (product_id) REFERENCES butcher_products(product_id)
            );
