CREATE TABLE IF NOT EXISTS restaurant_purchase_orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_number TEXT UNIQUE NOT NULL,
                supplier_id INTEGER NOT NULL,
                order_date DATE NOT NULL,
                expected_delivery_date DATE,
                actual_delivery_date DATE,
                total_cost REAL NOT NULL DEFAULT 0,
                tax_amount REAL DEFAULT 0,
                status TEXT DEFAULT 'Pending',
                payment_method TEXT,
                payment_status TEXT DEFAULT 'Unpaid',
                notes TEXT,
                created_by TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES restaurant_suppliers(supplier_id)
            );
