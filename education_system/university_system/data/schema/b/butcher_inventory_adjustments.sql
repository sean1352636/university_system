CREATE TABLE IF NOT EXISTS butcher_inventory_adjustments (
                        adjustment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER NOT NULL,
                        quantity_change REAL NOT NULL,
                        reason TEXT NOT NULL,
                        adjusted_by TEXT NOT NULL,
                        adjustment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT,
                        FOREIGN KEY (product_id) REFERENCES products(product_id)
                    );
