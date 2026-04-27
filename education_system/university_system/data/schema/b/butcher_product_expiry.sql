CREATE TABLE IF NOT EXISTS butcher_product_expiry (
                        expiry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER NOT NULL,
                        batch_number TEXT,
                        quantity_kg REAL NOT NULL,
                        expiry_date DATE NOT NULL,
                        received_date DATE DEFAULT CURRENT_DATE,
                        status TEXT DEFAULT 'active',
                        FOREIGN KEY (product_id) REFERENCES products(product_id)
                    );
