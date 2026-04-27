CREATE TABLE IF NOT EXISTS restaurant_waste (
                waste_id INTEGER PRIMARY KEY AUTOINCREMENT,
                waste_date DATE NOT NULL,
                item_name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit_of_measure TEXT,
                cost_value REAL NOT NULL,
                waste_type TEXT,
                reason TEXT NOT NULL,
                responsible_staff TEXT,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
