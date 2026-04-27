CREATE TABLE IF NOT EXISTS equipment_maintenance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            maintenance_type TEXT NOT NULL,
            description TEXT,
            performed_by TEXT,
            cost REAL DEFAULT 0,
            parts_replaced TEXT,
            hours_at_service INTEGER,
            next_service_hours INTEGER,
            service_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (equipment_id) REFERENCES equipment(id)
        );
