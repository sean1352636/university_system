CREATE TABLE IF NOT EXISTS facility_assets (
                asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_name TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                asset_tag TEXT UNIQUE,
                building_id INTEGER,
                room_id INTEGER,
                purchase_date TEXT,
                purchase_cost REAL,
                warranty_expiry TEXT,
                maintenance_schedule TEXT,
                last_maintenance_date TEXT,
                condition TEXT DEFAULT 'good',
                status TEXT DEFAULT 'active',
                FOREIGN KEY (building_id) REFERENCES buildings (building_id),
                FOREIGN KEY (room_id) REFERENCES rooms (id)
            );
