CREATE TABLE IF NOT EXISTS butcher_supplier_orders (
                supplier_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_name TEXT NOT NULL,
                order_date TEXT NOT NULL,
                expected_delivery TEXT,
                actual_delivery TEXT,
                status TEXT DEFAULT 'pending',
                total_cost DECIMAL(10,2),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT
            );
