CREATE TABLE IF NOT EXISTS cafe_supplier_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                cost_per_unit REAL,
                notes TEXT,
                FOREIGN KEY (supplier_id) REFERENCES cafe_suppliers(supplier_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            );
