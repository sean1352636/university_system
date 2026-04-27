CREATE TABLE IF NOT EXISTS housing_inventory (
            item_id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            item_type TEXT NOT NULL,
            condition TEXT NOT NULL,
            acquisition_date TEXT,
            status TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id)
        );
