CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            equipment_type TEXT NOT NULL,
            screen_number INTEGER,
            brand TEXT,
            model TEXT,
            serial_number TEXT,
            install_date TEXT,
            warranty_until TEXT,
            last_service_date TEXT,
            next_service_due TEXT,
            hours_used INTEGER DEFAULT 0,
            max_hours_before_service INTEGER DEFAULT 2000,
            status TEXT DEFAULT 'operational',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
