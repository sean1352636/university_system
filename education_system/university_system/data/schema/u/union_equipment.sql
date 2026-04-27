CREATE TABLE IF NOT EXISTS union_equipment (
            equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_name TEXT,
            category TEXT,
            description TEXT,
            serial_number TEXT,
            purchase_date TEXT,
            condition_status TEXT DEFAULT 'good',
            location TEXT,
            availability_status TEXT DEFAULT 'available',
            maintenance_due TEXT,
            replacement_cost REAL
        );
