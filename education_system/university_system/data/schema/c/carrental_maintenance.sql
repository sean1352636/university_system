CREATE TABLE IF NOT EXISTS carrental_maintenance (
                    maintenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id INTEGER NOT NULL,
                    maintenance_type TEXT NOT NULL,
                    description TEXT,
                    cost DECIMAL(10,2) DEFAULT 0,
                    service_date TEXT NOT NULL,
                    next_service_date TEXT,
                    mileage_at_service INTEGER,
                    performed_by TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vehicle_id) REFERENCES carrental_vehicles(vehicle_id)
                );
