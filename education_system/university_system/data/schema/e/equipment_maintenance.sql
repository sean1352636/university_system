CREATE TABLE IF NOT EXISTS equipment_maintenance (
                    maintenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL,
                    maintenance_type TEXT NOT NULL,
                    description TEXT,
                    cost DECIMAL(10,2) DEFAULT 0,
                    performed_date TEXT NOT NULL,
                    next_maintenance_date TEXT,
                    performed_by TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (item_id) REFERENCES equipment_items(item_id)
                );
