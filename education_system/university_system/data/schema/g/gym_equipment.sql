CREATE TABLE IF NOT EXISTS gym_equipment (
                    equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    brand TEXT,
                    model TEXT,
                    serial_number TEXT,
                    purchase_date DATE,
                    location TEXT,
                    status TEXT DEFAULT 'available',
                    last_maintenance DATE,
                    next_maintenance DATE,
                    notes TEXT
                );
