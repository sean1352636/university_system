CREATE TABLE IF NOT EXISTS purchase_orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_date TEXT,
                    total_amount REAL,
                    status TEXT DEFAULT 'pending',
                    vendor TEXT,
                    description TEXT,
                    department TEXT,
                    approved_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                , "actual_delivery" DATE, "expected_delivery" DATE, "notes" TEXT, "ordered_by" TEXT, "po_id" INTEGER, "po_number" TEXT, "received_by" TEXT, "shipping_cost" DECIMAL(10,2) DEFAULT 0, "supplier_id" INTEGER, "tax_amount" DECIMAL(10,2) DEFAULT 0, "updated_at" DATETIME DEFAULT CURRENT_TIMESTAMP);
